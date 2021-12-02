import requests
import json
from config import Config

class RemoteNodes(object):

    def __init__(self):
        self.nodes = Config().REMOTE_NODES

    """
    connect_to_node() func trying to connect to remote nodes.
    Returns "True" when first
    """
    def connect_to_node(self):
        for remoteNode in self.nodes:
            try:
                ping = json.loads(requests.get(remoteNode+'/remote-wallet/connectionPing').content)
                if ping['PING'] == True:
                    return remoteNode
            except:
                print(f'{remoteNode} is down.')

        return False
