import struct
from collections.abc import Callable

import objc
from AppKit import NSAppleEventManager
from Foundation import NSURL, NSObject

_kCoreEventClass = struct.unpack(">I", b"aevt")[0]
_kAEOpenDocuments = struct.unpack(">I", b"odoc")[0]
_keyDirectObject = struct.unpack(">I", b"----")[0]


class _OpenFileHandler(NSObject):
    def init(self) -> "_OpenFileHandler":
        self = objc.super(_OpenFileHandler, self).init()
        if self is not None:
            self._callback: Callable[[str], None] | None = None
        return self

    def handleOpenDocuments_withReplyEvent_(self, event, reply) -> None:
        desc = event.paramDescriptorForKeyword_(_keyDirectObject)
        for i in range(1, desc.numberOfItems() + 1):
            raw = desc.descriptorAtIndex_(i).stringValue()
            path = NSURL.URLWithString_(raw).path()
            if path and self._callback:
                self._callback(path)


_handler: _OpenFileHandler | None = None


def register_open_file_handler(callback: Callable[[str], None]) -> None:
    global _handler
    _handler = _OpenFileHandler.alloc().init()
    _handler._callback = callback
    mgr = NSAppleEventManager.sharedAppleEventManager()
    mgr.setEventHandler_andSelector_forEventClass_andEventID_(
        _handler,
        "handleOpenDocuments:withReplyEvent:",
        _kCoreEventClass,
        _kAEOpenDocuments,
    )
