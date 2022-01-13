import psycopg2
import codeshark_config as cfg
import atexit
from datetime import datetime

class DatabaseInitError(Exception):
	def __init__(self):
		super().__init__("Connection not established!")

class PGDB:
	""" """
	__inst = None
	__conn = None
	__error_handler = None
	__autocommit = None
	__logging = None
	__auto_shorten = None
	__silent = None
	error = None
	errormsg = None

	def __new__(cls, *args, **kwargs):
		if not cls.__inst:
			cls.__inst = super(PGDB, cls).__new__(cls)
		return cls.__inst

	def __init__(self, error_handler=None, autocommit=True, logging=True, auto_shorten=True, silent=False):
		if __class__.__conn:
			return

		__class__.__error_handler = error_handler
		__class__.__autocommit = autocommit
		__class__.__logging = logging
		__class__.__auto_shorten = auto_shorten
		__class__.__silent = silent

		cfg.load_config()

		__class__.__reconnect()
		if __class__.__conn.closed > 0 and not __class__.__silent:
			raise DatabaseInitError

		atexit.register(__class__.__cleanup)

	def __del__(self):
		__class__.__cleanup()

	@classmethod
	def __reconnect(cls):
		cls.__conn = psycopg2.connect(	database	= cfg.get_config("postgres_name"),
										host		= cfg.get_config("postgres_host"),
										user		= cfg.get_config("postgres_user"),
										password	= cfg.get_config("postgres_pass"))

	@classmethod
	def __cleanup(cls):
		try:
			cls.__conn.close()
			# cls.__logfile.close()
		except:
			pass

	@classmethod
	def debug(cls):
		print("conn >", cls.__conn)

	@classmethod
	def __log(cls, msg):
		if not cls.__logging: return
		# print(f">> {msg}")
		# cls.__logfile.write(msg)

	@classmethod
	def __seterror(cls, err):
		cls.error = type(err) if err is not None else None
		if err: cls.errormsg = err.pgerror

	@classmethod
	def error_handler(cls, func=None):
		if func:
			cls.__error_handler = func
		else:
			return cls.__error_handler

	@classmethod
	def del_error_handler(cls):
		cls.__error_handler = None

	@classmethod
	def autocommit(cls, autocommit=None):
		if autocommit is None:
			return cls.__autocommit
		else:
			cls.__autocommit = autocommit

	@classmethod
	def logging(cls, logging=None):
		if logging is None:
			return cls.__logging
		else:
			cls.__logging = logging

	@classmethod
	def auto_shorten(cls, auto_shorten=None):
		if auto_shorten is None:
			return cls.__auto_shorten
		else:
			cls.__auto_shorten = auto_shorten

	@classmethod
	def silent(cls, silent=None):
		if silent is None:
			return cls.__silent
		else:
			cls.__silent = silent

	@classmethod
	def commit(cls):
		cls.__conn.commit()
		cls.__log("commit")
	
	@classmethod
	def rollback(cls):
		cls.__conn.rollback()
		cls.__log("rollback")

	@classmethod
	def query(cls, query, *params):
		return cls.queryc(query, *params, autocommit=True)

	@classmethod
	def queryc(cls, query, *params, autocommit):
		cls.__reconnect()
		if cls.__conn.closed > 0 and not __class__.__silent:
			raise DatabaseInitError

		# Clear error status
		cls.__seterror(None)

		if not query.endswith(";"):
			query += ";"

		rows = None
		cur = None
		try:
			cur = cls.__conn.cursor()
			try:
				cur.execute(query, params)

				if autocommit and cls.__autocommit: # argument overrides global setting
					qq = query.strip().upper()
					for typ in ["INSERT", "UPDATE", "DELETE"]:
						if qq.startswith(typ):
							cls.commit()
							break

				rows = cur.fetchall()

				if cls.__auto_shorten:
					while type(rows) in [list, tuple] and len(rows) == 1:
						rows = rows[0]

				if type(rows) in [list, tuple] and len(rows) == 0: ## ?
					rows = None

			except Exception as err:
				try:
					cls.rollback()
				except Exception as err2:
					cls.__log(f"Rollback error: {err2};")

				cls.__seterror(err)
				cls.__log(f"Error while executing: {query}\nWith params: {params}\n{err}")
				
				if cls.__error_handler:
					cls.__error_handler(err)

		except Exception as err:
			cls.__seterror(err)
			cls.__log(f"Error creating cursor while executing: {query}\nWith params: {params}; ||{err}||")

		finally:
			del cur

		return [] if rows is None else rows ##
