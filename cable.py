"""Telegram caBLE(hybrid transport) 客户端 —— 对照 tdesktop webauthn/ 源码移植。

完整流程: 生成 QRKey + QR → 手机扫码 → BLE 扫描 advert → 解密 EID → tunnel 连接
→ Noise NKpsk0 握手 → 发送 makeCredential 请求(CTAP CBOR) → 收 credential。

密码学: P-256 ECDH + AES-256-GCM + AES-256-ECB + HKDF/HMAC-SHA256 + CBOR。
"""
import hashlib
import hmac
import secrets
import struct
import time

import cbor2
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# tunnel server 域名(官方 kAssignedTunnelDomains)
TUNNEL_DOMAINS = ["cable.ua5v.com", "cable.auth.com"]

# 常量(对照 cable_core.h)
K_P256_X962_LEN = 65
K_COMPRESSED_LEN = 33
K_QR_SECRET_SIZE = 16
K_ADVERT_SIZE = 20
K_EID_SIZE = 16
K_EID_KEY_SIZE = 64
K_NONCE_SIZE = 10
K_ROUTING_ID_SIZE = 3
K_TUNNEL_ID_SIZE = 16
K_PSK_SIZE = 32
K_HANDSHAKE_RESPONSE_SIZE = K_P256_X962_LEN + 16
K_PADDING_GRANULARITY = 16

NOISE_PROTOCOL = b"Noise_KNpsk0_P256_AESGCM_SHA256"


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _hmac_sha256(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def _hkdf(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    h = HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info)
    return h.derive(ikm)


def _gen_p256():
    return ec.generate_private_key(ec.SECP256R1())


def _pub_x962(priv, compressed: bool) -> bytes:
    fmt = (serialization.PublicFormat.CompressedPoint if compressed
           else serialization.PublicFormat.UncompressedPoint)
    return priv.public_key().public_bytes(serialization.Encoding.X962, fmt)


def _ecdh(priv, peer_x962: bytes) -> bytes:
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), peer_x962)
    return priv.exchange(ec.ECDH(), peer)


def _aes_gcm_seal(key32: bytes, nonce12: bytes, plaintext: bytes, aad: bytes) -> bytes:
    enc = Cipher(algorithms.AES(key32), modes.GCM(nonce12)).encryptor()
    enc.authenticate_additional_data(aad)
    return enc.update(plaintext) + enc.finalize() + enc.tag


def _aes_gcm_open(key32: bytes, nonce12: bytes, ciphertext: bytes, aad: bytes):
    tag = ciphertext[-16:]
    ct = ciphertext[:-16]
    dec = Cipher(algorithms.AES(key32), modes.GCM(nonce12, tag)).decryptor()
    dec.authenticate_additional_data(aad)
    return dec.update(ct) + dec.finalize()


def _aes_ecb_decrypt(key32: bytes, block16: bytes) -> bytes:
    dec = Cipher(algorithms.AES(key32), modes.ECB()).decryptor()
    return dec.update(block16) + dec.finalize()


def _derive(secret: bytes, nonce: bytes, type_val: int, size: int) -> bytes:
    info = struct.pack("<I", type_val)
    return _hkdf(secret, nonce, info, size)


# ---------- QR ----------
class QRKey:
    def __init__(self):
        self.identity = _gen_p256()
        self.secret = secrets.token_bytes(K_QR_SECRET_SIZE)


def bytes_to_digits(data: bytes) -> str:
    widths = [0, 3, 5, 8, 10, 13, 15, 17]
    out = []
    i, n = 0, len(data)
    while i < n:
        take = min(7, n - i)
        value = 0
        for j in range(take):
            value |= data[i + j] << (8 * j)
        out.append(str(value).zfill(widths[take]))
        i += take
    return ''.join(out)


def encode_qr_contents(key: QRKey, make_credential: bool, now: int) -> str:
    cbor_map = {
        0: _pub_x962(key.identity, True),
        1: key.secret,
        2: len(TUNNEL_DOMAINS),
        3: now,
        4: False,
        # 必须是 CBOR 文本字符串(0x62),与 tdesktop CborValue(std::string) 一致;
        # 用 bytes 会被编成字节字符串(0x42),Google 严格解析直接拒绝
        5: 'mc' if make_credential else 'ga',
    }
    return "FIDO:/" + bytes_to_digits(cbor2.dumps(cbor_map))


# ---------- Noise NKpsk0 ----------
class Noise:
    def __init__(self):
        self._ck = bytearray(NOISE_PROTOCOL)
        self._h = bytearray(NOISE_PROTOCOL)
        self._key = bytearray(32)
        self._nonce = 0

    def mix_hash(self, data: bytes):
        self._h = bytearray(_sha256(bytes(self._h) + data))

    def mix_key(self, ikm: bytes):
        out = _hkdf(ikm, bytes(self._ck), b'', 64)
        self._ck = bytearray(out[:32])
        self._key = bytearray(out[32:])
        self._nonce = 0

    def mix_key_and_hash(self, ikm: bytes):
        out = _hkdf(ikm, bytes(self._ck), b'', 96)
        self._ck = bytearray(out[:32])
        self.mix_hash(out[32:64])
        self._key = bytearray(out[64:96])
        self._nonce = 0

    def _nonce12(self):
        nonce = bytearray(12)
        nonce[0:4] = struct.pack(">I", self._nonce)
        self._nonce += 1
        return bytes(nonce)

    def encrypt_and_hash(self, plaintext: bytes) -> bytes:
        ct = _aes_gcm_seal(bytes(self._key), self._nonce12(), plaintext, bytes(self._h))
        self.mix_hash(ct)
        return ct

    def decrypt_and_hash(self, ciphertext: bytes):
        pt = _aes_gcm_open(bytes(self._key), self._nonce12(), ciphertext, bytes(self._h))
        if pt is not None:
            self.mix_hash(ciphertext)
        return pt

    def traffic_keys(self):
        out = _hkdf(b'', bytes(self._ck), b'', 64)
        return out[:32], out[32:]


class Crypter:
    def __init__(self, read_key: bytes, write_key: bytes):
        self._rk = read_key
        self._wk = write_key
        self._rs = 0
        self._ws = 0

    def _nonce(self, counter):
        nonce = bytearray(12)
        nonce[8:12] = struct.pack(">I", counter)
        return bytes(nonce)

    def encrypt(self, plaintext: bytes) -> bytes:
        padded_size = (len(plaintext) + 1 + K_PADDING_GRANULARITY - 1) & ~(K_PADDING_GRANULARITY - 1)
        padded = bytearray(padded_size)
        padded[:len(plaintext)] = plaintext
        padded[-1] = padded_size - len(plaintext) - 1
        ct = _aes_gcm_seal(self._wk, self._nonce(self._ws), bytes(padded), b'')
        self._ws += 1
        return ct

    def decrypt(self, ciphertext: bytes):
        pt = _aes_gcm_open(self._rk, self._nonce(self._rs), ciphertext, b'')
        if pt is None:
            return None
        self._rs += 1
        if not pt:
            return None
        padding = pt[-1]
        if padding + 1 > len(pt):
            return None
        return pt[:len(pt) - padding - 1]


class HandshakeInitiator:
    def __init__(self, psk32: bytes, identity):
        self._psk = psk32
        self._identity = identity
        self._noise = Noise()
        self._ephemeral = None

    def build_initial_message(self) -> bytes:
        self._noise = Noise()
        self._noise.mix_hash(b'\x01')
        self._noise.mix_hash(_pub_x962(self._identity, False))
        self._noise.mix_key_and_hash(self._psk)
        self._ephemeral = _gen_p256()
        eph_pub = _pub_x962(self._ephemeral, False)
        self._noise.mix_hash(eph_pub)
        self._noise.mix_key(eph_pub)
        ct = self._noise.encrypt_and_hash(b'')
        return eph_pub + ct

    def process_response(self, response: bytes):
        if len(response) != K_HANDSHAKE_RESPONSE_SIZE or not self._ephemeral:
            return None
        peer_point = response[:K_P256_X962_LEN]
        ciphertext = response[K_P256_X962_LEN:]
        self._noise.mix_hash(peer_point)
        self._noise.mix_key(peer_point)
        self._noise.mix_key(_ecdh(self._ephemeral, peer_point))
        self._noise.mix_key(_ecdh(self._identity, peer_point))
        pt = self._noise.decrypt_and_hash(ciphertext)
        if pt is None or pt:
            return None
        write_key, read_key = self._noise.traffic_keys()
        return Crypter(read_key, write_key)


# ---------- EID / advert ----------
def decrypt_advert(service_data: bytes, eid_key64: bytes):
    if len(service_data) < K_ADVERT_SIZE or len(eid_key64) != K_EID_KEY_SIZE:
        return None
    aes_key = eid_key64[:32]
    hmac_key = eid_key64[32:64]
    body = service_data[:16]
    tag = service_data[16:20]
    expected = _hmac_sha256(hmac_key, body)[:4]
    if tag != expected:
        return None
    plaintext = _aes_ecb_decrypt(aes_key, body)
    if plaintext[0] != 0:
        return None
    domain = plaintext[14] | (plaintext[15] << 8)
    if domain >= 256 or domain >= len(TUNNEL_DOMAINS):
        return None
    return plaintext


def eid_components(eid: bytes):
    nonce = eid[1:1 + K_NONCE_SIZE]
    routing_id = eid[1 + K_NONCE_SIZE:1 + K_NONCE_SIZE + K_ROUTING_ID_SIZE]
    domain = eid[14] | (eid[15] << 8)
    return nonce, routing_id, domain


def _hex_lower(data: bytes) -> str:
    return data.hex()


# ---------- CTAP ----------
def build_make_credential_request(client_data_hash32, rp_id, rp_name, user_id,
                                  user_name, user_display_name, algorithms):
    params = [{"alg": alg, "type": "public-key"} for alg in algorithms]
    cbor_map = {
        1: client_data_hash32,
        2: {"id": rp_id, "name": rp_name},
        3: {"id": user_id, "name": user_name, "displayName": user_display_name},
        4: params,
        7: {"rk": True, "uv": True},
    }
    return b'\x01' + cbor2.dumps(cbor_map)


def credential_id_from_auth_data(auth_data: bytes):
    prefix = 32 + 1 + 4
    if len(auth_data) < prefix + 16 + 2:
        return None
    flags = auth_data[32]
    if not (flags & 0x40):
        return None
    id_len = (auth_data[prefix + 16] << 8) | auth_data[prefix + 17]
    if len(auth_data) < prefix + 18 + id_len:
        return None
    return auth_data[prefix + 18:prefix + 18 + id_len]


def parse_make_credential_response(payload: bytes):
    if not payload or payload[0] != 0:
        return None
    try:
        parsed = cbor2.loads(payload[1:])
    except Exception:
        return None
    if not isinstance(parsed, dict) or 2 not in parsed:
        return None
    auth_data = parsed[2]
    cred_id = credential_id_from_auth_data(auth_data)
    if cred_id is None:
        return None
    return {"credentialId": cred_id, "authData": auth_data}


def parse_post_handshake_message(plaintext: bytes):
    revision = 1
    try:
        parsed = cbor2.loads(plaintext)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    supports_ctap = False
    features = parsed.get(3)
    if isinstance(features, list) and b'ctap' in features:
        supports_ctap = True
    return {"protocolRevision": revision, "supportsCtap": supports_ctap}


def b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def make_attestation_none(auth_data: bytes) -> bytes:
    """构造 fmt=none 的 attestationObject(对照 NoneAttestationObject)。"""
    return cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})


def make_client_data(challenge_b64url: str, type_str: str = "webauthn.create") -> str:
    """构造 clientDataJSON(对照 SerializeClientData)。"""
    import json as _j
    return _j.dumps({
        "type": type_str,
        "challenge": challenge_b64url,
        "origin": "https://telegram.org",
        "crossOrigin": False,
    }, separators=(',', ':'))


def parse_public_key_options(public_key_json: str) -> dict:
    """解析 Telegram 返回的 publicKey JSON(对照 DeserializeRegisterData)。

    返回 {rpId, rpName, userId, userName, userDisplayName, challenge(字符串), algorithms, clientDataJson, clientDataHash}
    """
    import base64
    import json as _j
    root = _j.loads(public_key_json)
    pk = root.get("publicKey", root)
    rp = pk.get("rp", {})
    user = pk.get("user", {})

    def _b64url_dec(s):
        s = s.replace('-', '+').replace('_', '/')
        pad = '=' * ((4 - len(s) % 4) % 4)
        return base64.b64decode(s + pad)

    user_id = _b64url_dec(user.get("id", ""))
    challenge_str = pk.get("challenge", "")
    algorithms = [p.get("alg") for p in pk.get("pubKeyCredParams", [])]
    client_data_json = make_client_data(challenge_str)
    client_data_hash = _sha256(client_data_json.encode('utf-8'))
    return {
        "rpId": rp.get("id", "telegram.org"),
        "rpName": rp.get("name", "Telegram Messenger"),
        "userId": user_id,
        "userName": user.get("name", ""),
        "userDisplayName": user.get("displayName", ""),
        "challenge": challenge_str,
        "algorithms": algorithms,
        "clientDataJson": client_data_json,
        "clientDataHash": client_data_hash,
    }


# ---------- 完整注册流程 ----------
_MSG_CTAP = 0x01
_CABLE_SERVICE_UUIDS = (
    "0000fde2-0000-1000-8000-00805f9b34fb",  # Google caBLE(旧)
    "0000fff9-0000-1000-8000-00805f9b34fb",  # FIDO caBLE(旧)
    "0000fcf1-0000-1000-8000-00805f9b34fb",  # Chromium caBLE(新,2024+)
)


async def register_via_cable(request: dict, qr_key=None, on_qr=None, on_state=None, timeout_s=90):
    """完整 caBLE 注册流程(异步)。request 字段见 build_make_credential_request。

    qr_key: 预生成的 QRKey(可选,不传则内部生成)。
    on_qr(text): 生成二维码后回调一次(仅内部生成时)。
    on_state(status): 进度回调('scanning'/'connecting'/'handshake'/'awaiting')。
    返回 {"credentialId": bytes, "authData": bytes} 或抛异常。
    """
    import asyncio
    import websockets
    from bleak import BleakScanner

    if qr_key is None:
        qr_key = QRKey()
        if on_qr:
            on_qr(encode_qr_contents(qr_key, True, int(time.time())))
    secret = qr_key.secret
    eid_key = _derive(secret, b'', 1, K_EID_KEY_SIZE)

    if on_state:
        on_state('scanning')

    # BLE 扫描,等待手机广播 caBLE advert
    loop = asyncio.get_event_loop()
    advert_future = loop.create_future()
    seen_payloads = set()

    def _try_accept(u, data):
        """用本会话密钥验广播负载;验过(hmac 正确)即视为本仪式的 EID。"""
        eid = decrypt_advert(data, eid_key)
        if eid is not None:
            if not advert_future.done():
                advert_future.set_result(eid)
            return True
        return False

    def _probe_variants(u, data):
        """标准解密失败时尝试变体布局,命中即回报(供离线分析格式)。"""
        if not on_state:
            return
        aes_key, hmac_key = eid_key[:32], eid_key[32:64]
        n = len(data)
        if n < 20:
            return
        candidates = []
        # 变体1: body 在任意偏移,tag 紧随其后
        for off in range(0, n - 19):
            body = data[off:off + 16]
            tag = data[off + 16:off + 20]
            candidates.append((off, body, tag))
        # 变体2: body 开头,tag 在末尾 4 字节
        candidates.append(('tail', data[:16], data[-4:]))
        for pos, body, tag in candidates:
            expected = _hmac_sha256(hmac_key, body)[:4]
            if tag == expected:
                pt = _aes_ecb_decrypt(aes_key, body)
                on_state(f'hit:{u}:pos={pos}:pt0={pt[0]}:pt={pt.hex()}')
                if pt[0] == 0:
                    domain = pt[14] | (pt[15] << 8)
                    if domain < len(TUNNEL_DOMAINS):
                        if not advert_future.done():
                            advert_future.set_result(pt)
                        return

    def _detect(_device, adv):
        if advert_future.done():
            return
        for uuid_str, data in (adv.service_data or {}).items():
            u = str(uuid_str).lower()
            b = bytes(data)
            key = (u, b)
            first_seen = key not in seen_payloads
            if first_seen:
                seen_payloads.add(key)
                if on_state:
                    rssi = getattr(adv, 'rssi', None)
                    on_state(f'adv:{u}:{len(b)}:{b.hex()}:{rssi}')
            # 无论什么 UUID,先按标准格式验一次(hmac 命中=本仪式广播)
            if len(b) >= K_ADVERT_SIZE and _try_accept(u, b):
                return
            if u in _CABLE_SERVICE_UUIDS and first_seen and len(b) >= K_ADVERT_SIZE:
                body = b[:16]
                tag = b[16:20]
                expected = _hmac_sha256(eid_key[32:64], body)[:4]
                pt = _aes_ecb_decrypt(eid_key[:32], body)
                domain = pt[14] | (pt[15] << 8)
                on_state(
                    f'diag:hmac={tag == expected},res0={pt[0] == 0},'
                    f'domain={domain},head={body[:4].hex()}')
            _probe_variants(u, b)
        # 厂商自定义数据(Google 可能换通道)
        for mid, mdata in (adv.manufacturer_data or {}).items():
            b = bytes(mdata)
            key = (f'mfg{mid}', b)
            if key not in seen_payloads:
                seen_payloads.add(key)
                if on_state:
                    on_state(f'mfg:{mid}:{len(b)}:{b.hex()}')
            if len(b) >= K_ADVERT_SIZE and _try_accept(f'mfg{mid}', b):
                return
            _probe_variants(f'mfg{mid}', b)

    scanner = BleakScanner(detection_callback=_detect)
    try:
        await scanner.start()
    except Exception as e:
        raise RuntimeError(f'蓝牙扫描启动失败(电脑需有蓝牙且开启): {e}')
    try:
        eid = await asyncio.wait_for(advert_future, timeout=timeout_s)
    except asyncio.TimeoutError:
        raise RuntimeError(
            f'等待手机扫码超时({timeout_s}s)。请确认电脑蓝牙已开启,且手机与电脑蓝牙可互相发现')
    finally:
        try:
            await scanner.stop()
        except Exception:
            pass

    nonce, routing_id, domain = eid_components(eid)
    tunnel_domain = TUNNEL_DOMAINS[domain]
    psk = _derive(secret, eid, 3, K_PSK_SIZE)
    tunnel_id = _derive(secret, b'', 2, K_TUNNEL_ID_SIZE)
    path = f"/cable/connect/{routing_id.hex()}/{tunnel_id.hex()}"

    if on_state:
        on_state('connecting')
    ws = await websockets.connect(
        f"wss://{tunnel_domain}{path}", subprotocols=["fido.cable"])

    try:
        handshake = HandshakeInitiator(psk, qr_key.identity)
        await ws.send(handshake.build_initial_message())
        response = await ws.recv()
        crypter = handshake.process_response(response)
        if crypter is None:
            raise RuntimeError('Noise 握手失败')

        if on_state:
            on_state('handshake')
        post = crypter.decrypt(await ws.recv())
        parsed = parse_post_handshake_message(post) if post else None
        if not parsed or not parsed['supportsCtap']:
            raise RuntimeError('手机不支持 CTAP')

        if on_state:
            on_state('awaiting')
        ctap_req = build_make_credential_request(
            request['clientDataHash'], request['rpId'], request['rpName'],
            request['userId'], request['userName'], request['userDisplayName'],
            request['algorithms'])
        await ws.send(crypter.encrypt(bytes([_MSG_CTAP]) + ctap_req))

        reply = crypter.decrypt(await ws.recv())
        if reply is None or not reply:
            raise RuntimeError('空响应')
        if reply[0] == _MSG_CTAP:
            reply = reply[1:]
        result = parse_make_credential_response(reply)
        if result is None:
            raise RuntimeError('注册被拒绝')
        return result
    finally:
        try:
            await ws.close()
        except Exception:
            pass
