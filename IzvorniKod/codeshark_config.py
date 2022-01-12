##############################
# Codeshark config manager
#
# - load_config(file=None)
# - save_config(file=None)
# - get_config(key)
# - set_config(key, value)
#
# TODO: Add actual logging
##############################

import json

DEFAULT_CFG = "codeshark.cfg"
_CFG_DATA = {}

class ConfigError(Exception):
	def __init__(self):
		super().__init__("Option doesn't exist!")

def load_config(file=None):
	""" """
	global _CFG_DATA

	if file == None:
		file = DEFAULT_CFG

	try:
		with open(file, encoding="utf-8") as fp:
			_CFG_DATA = json.loads(fp.read())

	except Exception as e: # Gotta catch em all
		#_CFG_DATA = {} # Potentially unwanted when config already loaded
		print(f"{e}")
		return False

	return True

def save_config(file=None):
	""" """
	if file == None:
		file = DEFAULT_CFG

	written = -1
	try:
		with open(file, "w", encoding="utf-8") as fp:
			written = fp.write(json.dumps(_CFG_DATA, indent=4, sort_keys=True))

	except Exception as e:
		print(f"{e}")

	return written

def get_config(key):
	""" """
	if key not in _CFG_DATA:
		#raise KeyError # hmmm
		raise ConfigError

	return _CFG_DATA[key]


def set_config(key, value):
	""" """
	global _CFG_DATA
	_CFG_DATA[key] = value
	return _CFG_DATA[key] # Echo
