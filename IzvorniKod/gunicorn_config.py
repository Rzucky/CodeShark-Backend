import multiprocessing as mp
import codeshark_config as cfg

cfg.load_config()

wsgi_app = "codeshark_backend:app"
bind = f"{cfg.get_config('flask_host')}:{cfg.get_config('flask_port')}"
workers = mp.cpu_count() * 2

if not cfg.get_config("debug"):
	certfile = cfg.get_config("certfile")
	keyfile = cfg.get_config("keyfile")
	#raw_env = ["FLASK_ENV=production"]
