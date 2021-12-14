import smtplib
from email.mime.text import MIMEText

import codeshark_config as cfg

cfg.load_config()

url 	 = cfg.get_config("mail_url")
username = cfg.get_config("mailtrap_user")
password = cfg.get_config("mailtrap_pass")

# currently sending to MailTrap for testing
def send_verification_mail(ime, prezime, email, token):
	sender = "CodeShark <noreply@domefan.club>"
	receiver = f"{ime} {prezime} <{email}>"

	message = f"""<h2>Welcome {ime} {prezime}!</h2></br>
	Thank you for signing up to CodeShark!</br>
	Please verify your email address by clicking the <a href = "{url + token}">here!</a></br></br>
	Please note that unverified accounts are automatically deleted in 1 hour after sign up.</br>
	If you didn't request this, please ignore this email."""

	msg = MIMEText(message, 'html')
	msg['Subject'] = 'CodeShark Mail Verification'
	msg['From'] = sender
	msg['To'] = receiver

	with smtplib.SMTP("smtp.mailtrap.io", 2525) as server:
		server.login(username, password)
		server.sendmail(sender, receiver,  msg.as_string())
