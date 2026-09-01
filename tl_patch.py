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
    return MessageNew
