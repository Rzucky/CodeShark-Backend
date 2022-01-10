import smtplib, ssl
from email.mime.text import MIMEText

import codeshark_config as cfg

cfg.load_config()

url 	 	= cfg.get_config("mail_url")
username 	= cfg.get_config("mail_username")
password	= cfg.get_config("mail_password")
smtp_server = cfg.get_config("smtp_server")
smtp_port 	= cfg.get_config("smtp_port")

# Create a secure SSL context
context = ssl.create_default_context()

# currently sending to MailTrap for testing
def send_verification_mail(name, last_name, email, token):

	message = f"""<h2>Welcome {name} {last_name}!</h2></br>
	Thank you for signing up to CodeShark!</br>
	Please verify your email address by clicking the <a href = "{url + token}">here!</a></br></br>
	Please note that unverified accounts are automatically deleted in 1 hour after sign up.</br>
	If you didn't request this, please ignore this email."""

	msg = MIMEText(message, 'html')
	msg['Subject'] = 'CodeShark Mail Verification'
	msg['From'] = username
	msg['To'] = email
	
	# this is considered secure
	with smtplib.SMTP(smtp_server, smtp_port) as server:
		server.starttls(context=context)
		server.login(username, password)
		server.sendmail(username, email,  msg.as_string())
