def gather(*args):
    return args


def get_event_loop():
    loop = object()
    setattr(loop, "close", lambda: None)
