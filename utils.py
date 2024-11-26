import datetime

def datetime_parser(dct):
    for k, v in dct.items():
        if isinstance(v, str):
            try:
                dct[k] = datetime.datetime.strptime(v, "%Y-%m-%d")
            except:
                pass
    return dct

def datetime_serializer(dct):
    for k, v in dct.items():
        if isinstance(v, datetime.datetime):
            try:
                dct[k] = datetime.datetime.strftime(v, "%Y-%m-%d")
            except:
                pass
    return dct