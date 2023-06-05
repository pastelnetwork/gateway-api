from enum import Enum


class DbStatus(str, Enum):
    NEW = "NEW"                     # just created record in DB
    UPLOADED = "UPLOADED"           # file uploaded to WN, and WN returned file_id/image_id
    PREBURN_FEE = "PREBURN_FEE"     # pre-burnt fee found in the preburn table or new one was sent and all confirmed
    STARTED = "STARTED"             # task started by WN, and WN returned task_id
    DONE = "DONE"                   # both registration and activation txid are received
    ERROR = "ERROR"                 # something went wrong, will try to re-process
    RESTARTED = "RESTARTED"         # task is scheduled to be reprocessed
    DEAD = "DEAD"                   # 10 re-processing attempts failed, will not try to re-process
    REGISTERED = "REGISTERED"       # task is registered, reg ticket txid is received


# Internal Life cycle of a request (DbStatus):
#
# (sense, cascade)  NEW -> UPLOADED -> PREBURN_FEE -> STARTED -> DONE
# (nft)             NEW -> UPLOADED -> STARTED -> DONE
#
# the request can go into error state at any of the above states
# ERROR -> RESTARTED -> UPLOADED -> PREBURN_FEE -> STARTED -> DONE
# ERROR, BUT has reg_txid -> REGISTERED
#
# REGISTERED -> DONE
#
# ERROR -> ... -> ERROR 10 times -> DEAD
