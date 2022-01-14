import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from selenium.common.exceptions import NoSuchElementException
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning) 
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--incognito")
chrome_options.add_argument("--log-level=3")
driver = webdriver.Chrome(executable_path=r"path_to_chromedriver.exe", options=chrome_options)
base_url = 'https://domefan.club'

@pytest.mark.parametrize('url', [base_url])
def test_home_page(url):
	driver.get(url)
	try:
		time.sleep(1)
		element = driver.find_element(By.CLASS_NAME, 'banner-description')
		time.sleep(1)
		assert True
	except:
		assert False

@pytest.mark.parametrize('url', [f"{base_url}/members"])
def test_memebers_page_not_logged_in(url):
	driver.get(url)
	# test should fail because it can't reach members page if not logged in
	# it should find the the login form
	try:
		time.sleep(1)
		element = driver.find_element(By.NAME, "username")
		time.sleep(1)
		assert True
	except NoSuchElementException:
		assert False

@pytest.mark.parametrize('url', [f"{base_url}/members"])
def test_memebers_page_logged_in(url):
	# first login
	driver.get(f'{base_url}/login')
	time.sleep(1)
	element = driver.find_element(By.NAME, "username")
	element.send_keys('obicansmrtnik1')
	time.sleep(.1)
	element = driver.find_element(By.NAME, "password")
	element.send_keys('smrtnik')
	driver.find_element(By.ID, "login-button").click()
	time.sleep(2)
	driver.find_element(By.CLASS_NAME, "swal2-confirm").click()
	time.sleep(2)

	# try to get members page
	driver.get(url)
	try:
		time.sleep(1)
		element = driver.find_element(By.CLASS_NAME, 'table-dark')
		time.sleep(1)
		assert True
	except NoSuchElementException:
		assert False

	time.sleep(1)
	driver.get(f'{base_url}/logout')

@pytest.mark.parametrize('username , password, expected_result',
	[('obicansmrtnik1', 'smrtnik', 'pass'), 
	('obicansmrtnik2', 'smrtnik', 'pass'), 
	('obicansmrtnik3', 'smrtnik', 'pass'), 
	('AlphaMale', 'alpha', 'pass'),  
	('SigmaMale', 'sigma', 'pass'), 
	('Ajvar','ajvar', 'pass'),
	('incorrect_username', 'whatever', 'fail'),
	('obicansmrtnik3', 'wrong_password', 'fail')])
def test_login_page(username, password, expected_result):

	driver.get(f'{base_url}/login')
	time.sleep(1)
	element = driver.find_element(By.NAME, "username")
	element.send_keys(username)
	time.sleep(.1)
	element = driver.find_element(By.NAME, "password")
	element.send_keys(password)
	driver.find_element(By.ID, "login-button").click()
	time.sleep(1)
	text = (driver.find_element(By.XPATH,'/html/body/div[2]/div/h2/p')).text
	time.sleep(1)

	# sometimes the expected result is to fail
	if text == 'Successfully signed in!':
		assert expected_result == 'pass'
	elif text == 'Could not sign in!':
		assert expected_result == 'fail'
	else:
		assert False

	driver.get(f'{base_url}/logout')

@pytest.mark.parametrize('url', [f"{base_url}/profile"])
def test_profile_page_not_logged_in(url):
	driver.get(url)
	# the page should redirect to the login form
	try:
		time.sleep(1)
		element = driver.find_element(By.NAME, "username")
		time.sleep(1)
		assert True
	except NoSuchElementException:
		assert False

@pytest.mark.parametrize('url', [f"{base_url}/profile"])
def test_profile_page_logged_in(url):
	# first login
	driver.get(f'{base_url}/login')
	time.sleep(1)
	element = driver.find_element(By.NAME, "username")
	element.send_keys('obicansmrtnik1')
	time.sleep(.1)
	element = driver.find_element(By.NAME, "password")
	element.send_keys('smrtnik')
	driver.find_element(By.ID, "login-button").click()
	time.sleep(2)
	driver.find_element(By.CLASS_NAME, "swal2-confirm").click()
	time.sleep(2)

	driver.get(url)
	try:
		time.sleep(1)
		element = driver.find_element(By.ID, 'avatar-profile')
		time.sleep(1)
		assert True
	except NoSuchElementException:
		assert False

	driver.get(f'{base_url}/logout')
