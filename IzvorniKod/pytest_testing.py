import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from selenium.common.exceptions import NoSuchElementException
import warnings
import psycopg2.extensions

from codeshark_backend import connect_to_db
from classes import User, Competition, Task

warnings.filterwarnings("ignore", category=DeprecationWarning) 
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--incognito")
chrome_options.add_argument("--log-level=3")
driver = webdriver.Chrome(executable_path=r"path_to_chromedriver", options=chrome_options)
base_url = 'https://domefan.club'

####### system tests

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


####### unit tests

@pytest.mark.parametrize('expected_type', [psycopg2.extensions.connection])
def test_db_connection(expected_type):
	conn, _ = connect_to_db()
	assert isinstance(conn, expected_type)
	conn.close()

@pytest.mark.parametrize('username, email, expected_result', 
	[('obicansmrtnik1', 'obicansmrtnik@ffzg.hr', True), 
	('incorrect_username', 'incorrect_username@fer.hr', False)])
def test_check_if_user_exists(username, email, expected_result):
	conn, cursor = connect_to_db()
	existence = User.check_if_user_exists(cursor, username, email)[0]
	assert existence == expected_result
	conn.close()

@pytest.mark.parametrize('class_id, expected_result', [(1, 'amater'), (7, None)])
def test_get_class_name(class_id, expected_result):
	conn, cursor = connect_to_db()
	name = Competition.get_class_name_from_class_id(cursor, class_id)[0]
	# This shouldn't be done when comparing with None (should be "is None") 
	# but to simplify this example
	assert name == expected_result
	conn.close()

@pytest.mark.parametrize('slug, expected_result_type', [('area-of-a-sphere', Task), ('wrong-slug', type(None))])
def test_get_task(slug, expected_result_type):
	conn, cursor = connect_to_db()
	task, _ = Task.get_task(cursor, slug)
	# we can't use isinstance in this case as it can't compare when task is None 
	assert type(task) == expected_result_type
	conn.close()
