import os
import time
import requests
import urllib3
import urllib.request
import urllib.parse
import json
from bs4 import BeautifulSoup
import re
import html 
import psycopg2
import psycopg2.extras
import calendar
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# Desativa os avisos vermelhos de SSL no terminal gerados pelo Proxy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from fastapi import FastAPI, APIRouter, HTTPException, status, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

# --- CONFIGURAÇÃO DE PROXY DO ITPS ---
proxy_url = "http://auditorio.itps:auditorio2023@proxy.itps.gov-se:8080"

os.environ['HTTP_PROXY'] = proxy_url
os.environ['HTTPS_PROXY'] = proxy_url
os.environ['http_proxy'] = proxy_url
os.environ['https_proxy'] = proxy_url
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1,itps.se.gov.br,172.23.6.109'
os.environ['no_proxy'] = 'localhost,127.0.0.1,::1,itps.se.gov.br,172.23.6.109'

# --- CONFIGURAÇÕES DE CONEXÃO POSTGRES ---
PG_HOST = "172.23.6.109"
PG_PORT = 5432
PG_USER = "geinform"
PG_PASSWORD = "intr@bd109"
PG_DB = "bd_intranet"
