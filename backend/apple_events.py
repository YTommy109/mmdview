import struct
import sys
import traceback
from collections.abc import Callable

if sys.platform != "darwin":
    raise ImportError("backend.apple_events is macOS only")

import objc
from AppKit import NSAppleEventManager
from Foundation import NSObject

from backend.logger import logger

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
        logger.info("handleOpenDocuments_withReplyEvent_ called")
        try:
            desc = event.paramDescriptorForKeyword_(_keyDirectObject)
            count = desc.numberOfItems()
            logger.info("odoc event: %d item(s)", count)
            for i in range(1, count + 1):
                url = desc.descriptorAtIndex_(i).fileURLValue()
                if url is None:
                    logger.warning("descriptorAtIndex_(%d).fileURLValue() returned None", i)
                    continue
                path = url.path()
                logger.info("received path[%d]: %s", i, path)
                if path and self._callback:
                    self._callback(path)
        except Exception:
            logger.error(
                "exception in handleOpenDocuments_withReplyEvent_:\n%s",
                traceback.format_exc(),
            )


_handler: _OpenFileHandler | None = None


def register_open_file_handler(callback: Callable[[str], None]) -> None:
    logger.info("register_open_file_handler called")
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
    logger.info("Apple Event handler registered successfully")
