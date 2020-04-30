_logger_filepath = ''


_can_log = False


def create_log(filepath, can_log):
    global _logger_filepath, _can_log
    _can_log = can_log
    if can_log:
        _logger_filepath = filepath + '.log'
        f = open(_logger_filepath, 'w+')
        f.close()


def log(text):
    global _logger_filepath, _can_log
    if _can_log:
        f = open(_logger_filepath, 'a+')
        f.write(text + '\n')
        f.close()
