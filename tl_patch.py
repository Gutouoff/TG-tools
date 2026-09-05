"""Telethon 1.44 (layer 227) 新版 message 构造体补丁 (2026-09-01)

背景: Telegram 服务器 schema 更新了 message 构造体:
  旧 (Telethon 1.44 内置):  7600b9d3  —— 含 guestchat_via_from(flags2.19) / rich_message(flags2.13)
  新 (服务器现在返回):      3ae56482  —— 删掉了这两个字段
拉取含新版消息的对话(如 Uau 号的垃圾对话)会 TypeNotFoundError 崩溃。
PyPI 最新的 Telethon 1.44 (2026-06-15) 尚未跟进,layer 227 落后服务器。

方案: 按官方 schema 手写新版构造体的 from_reader (逐字节对齐),
继承 telethon.tl.patched.Message (保留全部 custom 语法糖),
注册进 telethon.tl.alltlobjects.tlobjects 解析表。
"""
from telethon.tl import alltlobjects
from telethon.tl.patched import Message as PatchedMessage
from telethon.tl.types import User


class MessageNew(PatchedMessage):
    """新版 message#3ae56482 = 旧版去掉 guestchat_via_from / rich_message。"""
    CONSTRUCTOR_ID = 0x3ae56482
    SUBCLASS_OF_ID = 0x790009e3

    @classmethod
    def from_reader(cls, reader):
        flags = reader.read_int()
        _out = bool(flags & 2)
        _mentioned = bool(flags & 16)
        _media_unread = bool(flags & 32)
        _silent = bool(flags & 8192)
        _post = bool(flags & 16384)
        _from_scheduled = bool(flags & 262144)
        _legacy = bool(flags & 524288)
        _edit_hide = bool(flags & 2097152)
        _pinned = bool(flags & 16777216)
        _noforwards = bool(flags & 67108864)
        _invert_media = bool(flags & 134217728)
        flags2 = reader.read_int()
        _offline = bool(flags2 & 2)
        _video_processing_pending = bool(flags2 & 16)
        _paid_suggested_post_stars = bool(flags2 & 256)
        _paid_suggested_post_ton = bool(flags2 & 512)
        _id = reader.read_int()
        _from_id = reader.tgread_object() if flags & 256 else None
        _from_boosts_applied = reader.read_int() if flags & 536870912 else None
        _from_rank = reader.tgread_string() if flags2 & 4096 else None
        _peer_id = reader.tgread_object()
        _saved_peer_id = reader.tgread_object() if flags & 268435456 else None
        _fwd_from = reader.tgread_object() if flags & 4 else None
        _via_bot_id = reader.read_long() if flags & 2048 else None
        _via_business_bot_id = reader.read_long() if flags2 & 1 else None
        # 注意: 新版没有 guestchat_via_from (flags2 & 524288)
        _reply_to = reader.tgread_object() if flags & 8 else None
        _date = reader.tgread_date()
        _message = reader.tgread_string()
        _media = reader.tgread_object() if flags & 512 else None
        _reply_markup = reader.tgread_object() if flags & 64 else None
        if flags & 128:
            reader.read_int()
            _entities = [reader.tgread_object()
                         for _ in range(reader.read_int())]
        else:
            _entities = None
        _views = reader.read_int() if flags & 1024 else None
        _forwards = reader.read_int() if flags & 1024 else None
        _replies = reader.tgread_object() if flags & 8388608 else None
        _edit_date = reader.tgread_date() if flags & 32768 else None
        _post_author = reader.tgread_string() if flags & 65536 else None
        _grouped_id = reader.read_long() if flags & 131072 else None
        _reactions = reader.tgread_object() if flags & 1048576 else None
        if flags & 4194304:
            reader.read_int()
            _restriction_reason = [reader.tgread_object()
                                   for _ in range(reader.read_int())]
        else:
            _restriction_reason = None
        _ttl_period = reader.read_int() if flags & 33554432 else None
        _quick_reply_shortcut_id = reader.read_int() if flags & 1073741824 else None
        _effect = reader.read_long() if flags2 & 4 else None
        _factcheck = reader.tgread_object() if flags2 & 8 else None
        _report_delivery_until_date = reader.tgread_date() if flags2 & 32 else None
        _paid_message_stars = reader.read_long() if flags2 & 64 else None
        _suggested_post = reader.tgread_object() if flags2 & 128 else None
        _schedule_repeat_period = reader.read_int() if flags2 & 1024 else None
        _summary_from_language = reader.tgread_string() if flags2 & 2048 else None
        # 注意: 新版没有 rich_message (flags2 & 8192)
        obj = cls(id=_id, peer_id=_peer_id, message=_message, date=_date,
                  out=_out, mentioned=_mentioned, media_unread=_media_unread,
                  silent=_silent, post=_post, from_scheduled=_from_scheduled,
                  legacy=_legacy, edit_hide=_edit_hide, pinned=_pinned,
                  noforwards=_noforwards, invert_media=_invert_media,
                  offline=_offline,
                  video_processing_pending=_video_processing_pending,
                  paid_suggested_post_stars=_paid_suggested_post_stars,
                  paid_suggested_post_ton=_paid_suggested_post_ton,
                  from_id=_from_id,
                  from_boosts_applied=_from_boosts_applied,
                  from_rank=_from_rank,
                  saved_peer_id=_saved_peer_id, fwd_from=_fwd_from,
                  via_bot_id=_via_bot_id,
                  via_business_bot_id=_via_business_bot_id,
                  reply_to=_reply_to, media=_media,
                  reply_markup=_reply_markup, entities=_entities,
                  views=_views, forwards=_forwards, replies=_replies,
                  edit_date=_edit_date, post_author=_post_author,
                  grouped_id=_grouped_id, reactions=_reactions,
                  restriction_reason=_restriction_reason,
                  ttl_period=_ttl_period,
                  quick_reply_shortcut_id=_quick_reply_shortcut_id,
                  effect=_effect, factcheck=_factcheck,
                  report_delivery_until_date=_report_delivery_until_date,
                  paid_message_stars=_paid_message_stars,
                  suggested_post=_suggested_post,
                  schedule_repeat_period=_schedule_repeat_period,
                  summary_from_language=_summary_from_language)
        obj.flags = flags
        obj.flags2 = flags2
        return obj


def apply():
    """注册新构造体到 Telethon 解析表。幂等,重复调用安全。"""
    if 0x3ae56482 not in alltlobjects.tlobjects:
        alltlobjects.tlobjects[0x3ae56482] = MessageNew
    if 0xb1b8cc83 not in alltlobjects.tlobjects:
        alltlobjects.tlobjects[0xb1b8cc83] = UserNew
    return MessageNew


class UserNew(User):
    """新版 user#b1b8cc83 (2026-09, layer 227 之后): 与旧版 user#31774388
    字段布局完全一致,仅在尾部新增 linked_community_id:flags2.21?long。
    服务器在 GetUsers 响应里已开始返回此构造体,Telethon 1.44 不识别,
    导致刷新账号资料时 'Could not find a matching Constructor ID b1b8cc83'。"""
    CONSTRUCTOR_ID = 0xb1b8cc83
    SUBCLASS_OF_ID = 0x2da17977

    @classmethod
    def from_reader(cls, reader):
        flags = reader.read_int()
        flags2 = reader.read_int()
        _is_self = bool(flags & 1024)
        _contact = bool(flags & 2048)
        _mutual_contact = bool(flags & 4096)
        _deleted = bool(flags & 8192)
        _bot = bool(flags & 16384)
        _bot_chat_history = bool(flags & 32768)
        _bot_nochats = bool(flags & 65536)
        _verified = bool(flags & 131072)
        _restricted = bool(flags & 262144)
        _min = bool(flags & 1048576)
        _bot_inline_geo = bool(flags & 2097152)
        _support = bool(flags & 8388608)
        _scam = bool(flags & 16777216)
        _apply_min_photo = bool(flags & 33554432)
        _fake = bool(flags & 67108864)
        _bot_attach_menu = bool(flags & 134217728)
        _premium = bool(flags & 268435456)
        _attach_menu_enabled = bool(flags & 536870912)
        _bot_can_edit = bool(flags2 & 2)
        _close_friend = bool(flags2 & 4)
        _stories_hidden = bool(flags2 & 8)
        _stories_unavailable = bool(flags2 & 16)
        _contact_require_premium = bool(flags2 & 1024)
        _bot_business = bool(flags2 & 2048)
        _bot_has_main_app = bool(flags2 & 8192)
        _bot_forum_view = bool(flags2 & 65536)
        _bot_forum_can_manage_topics = bool(flags2 & 131072)
        _bot_can_manage_bots = bool(flags2 & 262144)
        _bot_guestchat = bool(flags2 & 524288)
        _bot_guard = bool(flags2 & 1048576)
        _id = reader.read_long()
        _access_hash = reader.read_long() if flags & 1 else None
        _first_name = reader.tgread_string() if flags & 2 else None
        _last_name = reader.tgread_string() if flags & 4 else None
        _username = reader.tgread_string() if flags & 8 else None
        _phone = reader.tgread_string() if flags & 16 else None
        _photo = reader.tgread_object() if flags & 32 else None
        _status = reader.tgread_object() if flags & 64 else None
        _bot_info_version = reader.read_int() if flags & 16384 else None
        if flags & 262144:
            reader.read_int()
            _restriction_reason = [reader.tgread_object()
                                   for _ in range(reader.read_int())]
        else:
            _restriction_reason = None
        _bot_inline_placeholder = (reader.tgread_string()
                                   if flags & 524288 else None)
        _lang_code = reader.tgread_string() if flags & 4194304 else None
        _emoji_status = reader.tgread_object() if flags & 1073741824 else None
        if flags2 & 1:
            reader.read_int()
            _usernames = [reader.tgread_object()
                          for _ in range(reader.read_int())]
        else:
            _usernames = None
        _stories_max_id = reader.tgread_object() if flags2 & 32 else None
        _color = reader.tgread_object() if flags2 & 256 else None
        _profile_color = reader.tgread_object() if flags2 & 512 else None
        _bot_active_users = reader.read_int() if flags2 & 4096 else None
        _bot_verification_icon = reader.read_long() if flags2 & 16384 else None
        _send_paid_messages_stars = (reader.read_long()
                                     if flags2 & 32768 else None)
        _linked_community_id = reader.read_long() if flags2 & 2097152 else None
        obj = cls(id=_id, is_self=_is_self, contact=_contact,
                  mutual_contact=_mutual_contact, deleted=_deleted, bot=_bot,
                  bot_chat_history=_bot_chat_history, bot_nochats=_bot_nochats,
                  verified=_verified, restricted=_restricted, min=_min,
                  bot_inline_geo=_bot_inline_geo, support=_support,
                  scam=_scam, apply_min_photo=_apply_min_photo, fake=_fake,
                  bot_attach_menu=_bot_attach_menu, premium=_premium,
                  attach_menu_enabled=_attach_menu_enabled,
                  bot_can_edit=_bot_can_edit, close_friend=_close_friend,
                  stories_hidden=_stories_hidden,
                  stories_unavailable=_stories_unavailable,
                  contact_require_premium=_contact_require_premium,
                  bot_business=_bot_business,
                  bot_has_main_app=_bot_has_main_app,
                  bot_forum_view=_bot_forum_view,
                  bot_forum_can_manage_topics=_bot_forum_can_manage_topics,
                  bot_can_manage_bots=_bot_can_manage_bots,
                  bot_guestchat=_bot_guestchat, bot_guard=_bot_guard,
                  access_hash=_access_hash, first_name=_first_name,
                  last_name=_last_name, username=_username, phone=_phone,
                  photo=_photo, status=_status,
                  bot_info_version=_bot_info_version,
                  restriction_reason=_restriction_reason,
                  bot_inline_placeholder=_bot_inline_placeholder,
                  lang_code=_lang_code, emoji_status=_emoji_status,
                  usernames=_usernames, stories_max_id=_stories_max_id,
                  color=_color, profile_color=_profile_color,
                  bot_active_users=_bot_active_users,
                  bot_verification_icon=_bot_verification_icon,
                  send_paid_messages_stars=_send_paid_messages_stars)
        obj.linked_community_id = _linked_community_id
        obj.flags = flags
        obj.flags2 = flags2
        # 服务器 schema 可能比已知定义更新: 实测 2026-09 的 GetUsers 响应里,
        # user#b1b8cc83 已知字段后还带 16 字节未知尾部。不消费会破坏外层
        # (Vector 等容器)的同步解析。只在"小段且 4 字节对齐"时跳过——
        # 大段剩余更可能是解析错位或外层还有别的对象,留给上层报错。
        try:
            left = len(reader.stream) - reader.position
            if 0 < left <= 64 and left % 4 == 0:
                obj.unknown_tail = reader.read(left)
        except Exception:
            pass
        return obj
