_logger_filepath = ''


_can_log = False

# Kept open for the whole export instead of being opened/closed on every single log() call (that was one of the biggest, easiest-to-fix causes of slow exports on machines with slow disks: previously every logged primitive/polygon did its own open()+close() syscall pair).
_log_file = None


def create_log(filepath, can_log):
    global _logger_filepath, _can_log, _log_file
    _can_log = can_log
    if can_log:
        _logger_filepath = filepath + '.log'
        _log_file = open(_logger_filepath, 'w+')


def close_log():
    """Call this once when the export finishes (success or failure) to
    flush and release the log file handle."""
    global _log_file
    if _log_file is not None:
        _log_file.close()
        _log_file = None


def log(text, debug_only=True):
    """Log a message.

    debug_only=True (the default) means the message is only printed to the
    console / written to the log file when logging is enabled via
    create_log(..., can_log=True). Previously every call to log() always
    printed to the console regardless of the user's "Generate log file"
    setting, which meant every skipped n-gon/line/primitive during export
    produced console I/O even when the user didn't ask for it. Pass
    debug_only=False for messages that should always be visible (e.g. real
    warnings/errors).
    """
    global _log_file, _can_log

    if not _can_log and debug_only:
        return

    print(text)
    if _can_log and _log_file is not None:
        _log_file.write(text + '\n')
