_logger_filepath = ''


def create_log(filepath):
    global _logger_filepath
    _logger_filepath = filepath + '.log'
    f = open(_logger_filepath, 'w+')
    f.close()


def log(text):
    global _logger_filepath
    f = open(_logger_filepath, 'a+')
    f.write(text + '\n')
    f.close()
