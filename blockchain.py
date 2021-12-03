import requests
import json
from config import Config


class Account(object):
    def __init__(self):
        self.address = None
        self.balance = None
        self.blockHash = None
        self.validHash = None
        self.slt = None


class Blockchain(object):
    def __init__(self):
        self.cnfg = Config()
        self.chain=[]
        self.accounts=[]
        self.nodes = Config().REMOTE_NODES
        self.prkey = None
        self.pubKey = None


    def connect_to_node(self):

        """
        connect_to_node() func trying to connect to remote nodes.
        Returns "True" when first
        """

        for remoteNode in self.nodes:
            try:
                ping = json.loads(requests.get(remoteNode+'/remote-wallet/connectionPing').content)
                if ping['PING'] == True:
                    return remoteNode
            except:
                print(f'{remoteNode} is down.')

        return False
