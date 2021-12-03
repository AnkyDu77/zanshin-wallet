import os
import hashlib

from Crypto.PublicKey import RSA
from config import Config

def authoriseUser(password):

    """
    Gets user password and opens prKey file which suits for the password.
    Returns:
        (a) public key, private key and wallet address if password is correct;
        (b) False, False, False if password is incorrect or there is no wallets files.

    """
    fileNames = os.listdir(os.path.join(Config().BASEDIR, 'keys'))
    try:
        prKeyNames = [name for name in fileNames if name.split('_')[1] == 'prKey.der']

    except:
        return False, False, False

    for prKeyName in prKeyNames:
        try:
            with open(os.path.join(os.path.join(Config().BASEDIR, 'keys'), prKeyName), 'rb') as keyFile:
                key = RSA.import_key(keyFile.read(), passphrase=password)
            prKey = key.export_key()
            pubKey = key.public_key().export_key(format='DER')

            pubHash = hashlib.sha3_224(pubKey).hexdigest()
            address = Config().IDSTR+pubHash

            return pubKey, prKey, address

        except:
            pass

    return False, False, False
