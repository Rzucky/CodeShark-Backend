import smtplib, ssl
from email.mime.text import MIMEText

import codeshark_config as cfg

cfg.load_config()

url 	 			= cfg.get_config("mail_url")
username 			= cfg.get_config("mail_username")
password			= cfg.get_config("mail_password")
smtp_server 		= cfg.get_config("smtp_server")
smtp_port 			= cfg.get_config("smtp_port")

rank_upgrade_url 	= cfg.get_config("rank_upgrade_url")
admin_mail 			= cfg.get_config("admin_mail")

# Create a secure SSL context
context = ssl.create_default_context()

# sending verification emails to users
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

# sending upgrade mails to admin mail to change a competitor to leader
def send_upgrade_mail(user):

	message = f"""<h3> User {user.name} {user.last_name} ({user.username})</h3>
				<h4> wants to be a competition leader </h4></br>
				<a href = "{rank_upgrade_url + user.username}">
				Press here to upgrade their rank on their profile</a>
				</br></br> Codeshark"""

	msg = MIMEText(message, 'html')
	msg['Subject'] = 'CodeShark Competition Leader Upgrade'
	msg['From'] = username
	msg['To'] = admin_mail

	with smtplib.SMTP(smtp_server, smtp_port) as server:
		server.starttls(context=context)
		server.login(username, password)
		server.sendmail(username, admin_mail,  msg.as_string())
