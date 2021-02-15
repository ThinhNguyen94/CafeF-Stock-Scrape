from django.shortcuts import render
from django.http import HttpResponse

from django.template.defaulttags import register 
from json import dumps 

#Import some libraries for scrapping
#import requests
from urllib.request import urlopen
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys 
from selenium.webdriver.common.by import By 
from selenium.webdriver.support.ui import WebDriverWait 
from selenium.webdriver.support import expected_conditions as EC 
import time
import datetime
import math

# Libraries for data wrangling and statistics 
import pandas as pd
import numpy as np 
from scipy.stats import skew,kurtosis

####---------------------------------------------------------VIEWS---------------------------------------------------

@register.filter
def get_range(value,arg):
    return range(arg,value)

@register.filter
def get_element_by_index(value, arg):
    return value[arg]

# Return stock info view on the home page

def HomePage(request):
    return render(request, 'scrape/home.html')

# Class to store current data
class dataOnLoad:
    def __init__(self):
        self.__quote=None
        self.__sdate=None
        self.__edate=None
        self.__content={'submitbutton':''}
    def set_quote(self, quote):
        self.__quote=quote
    def set_sdate(self, sdate):
        self.__sdate = sdate
    def set_edate(self, edate):
        self.__edate = edate
    def set_content(self, content):
        self.__content = content
    def get_quote(self):
        return self.__quote
    def get_sdate(self):
        return self.__sdate
    def get_edate(self):
        return self.__edate
    def get_content(self):
        return self.__content

info_current = dataOnLoad()


def ScrapeInfo(request):
    
    content = info_current.get_content()
    quote_tmp = info_current.get_quote()
    sdate_tmp = info_current.get_sdate()
    edate_tmp = info_current.get_edate()
    if request.method == 'GET':
        quote = request.GET.get('quote')
        sdate = request.GET.get('date_from')
        edate = request.GET.get('date_to')
        if quote_tmp==quote and sdate_tmp==sdate and edate_tmp==edate:
            return render(request, 'scrape/home.html', content)
        
        info_current.set_quote(quote)
        info_current.set_edate(edate)
        info_current.set_sdate(sdate)
        
        submitbutton = request.GET.get('Scrape')
        data = CafefStockScrape(quote.upper(), sdate, edate)
        options = webdriver.ChromeOptions()
        options.add_argument('headless')
        PATH = 'C:\chromedriver.exe'
        driver = webdriver.Chrome(PATH, options=options)
        data.scrape_stock(driver)
        nrows = data.get_nrows()
        numPageView = math.ceil(nrows/20)
        data.remove_xa0()   # remove '\xa0'
        data = data.get_scrapped_data()
        data = data.to_dict('list')
        keys = list(data.keys())
        content['submitbutton'] = "Submit"
        content['keys'] = keys
        content['data'] = data
        content['quote'] = quote
        content['sdate'] = sdate
        content['edate'] = edate
        content['nrows'] = nrows

        # dump data
        dataJSON = dumps(content)
        content['dataJSON'] = dataJSON

        info_current.set_content(content) # store current content
    
    return render(request, 'scrape/home.html', content)

# Return summary statistics of the stock
def Summary_stat(request):
    content = info_current.get_content()
    if content['submitbutton']=='':
      return render(request, 'scrape/stat.html', content)
    data_in = pd.Series(content['data']['Giá đóng cửa']).str.replace(',','')
    data_in = data_in.astype(float)
    info_stat = StockStat(data_in)
    stat_output = {
      'meanPrice': info_stat.get_meanPrice(),
      'stdPrice': info_stat.get_stdPrice(),
      'skewPrice': info_stat.get_skewPrice(),
      'kurtPrice': info_stat.get_kurtPrice(),
      'meanLR': info_stat.get_meanLogReturn(),
      'stdLR': info_stat.get_stdLogReturn(),
      'skewLR': info_stat.get_skewLogReturn(),
      'kurtLR': info_stat.get_kurtLogReturn()
    }
    content['stat_output'] = stat_output
    return render(request, 'scrape/stat.html', content)


###----------------------------------------------------------LOGIC CLASSES--------------------------------------------

## Class for Scraping Historical Stock Price on cafef.vn
class CafefStockScrape:

    ## Constructor
    def __init__(self, quote, start_date, end_date):
        self.__quote = quote
        self.__start_date = start_date
        self.__end_date = end_date
        self.__url = "https://s.cafef.vn/Lich-su-giao-dich-{}-1.chn".format(quote)
        self.__data = [] # placeholder for data
    
    # function to scrape data on the present page 
    def __get_data(self, bs):
        '''
            bs: BeautifulSoup object of a url
        '''
        stock_data=[]   # placeholder for scraped data
        tr_tags = bs.find('table',id="GirdTable2").find_all('tr')  # list of all <tr> tags
        for tr in tr_tags:
            if tr.has_attr('id'):
                id_tag = tr['id']
                if 'ctl00_ContentPlaceHolder1_ctl03_rptData2' in id_tag:
                    td_tags = tr.find_all('td')
                    i=1
                    value = []
                    for td in td_tags:
                        if td['class'][0] != "Item_Image" and i<=10:
                            value.append(td.get_text())
                            i+=1
                    stock_data.append(value)

        stock_info = pd.DataFrame(stock_data,columns=['Ngày','Giá đóng cửa','Thay đổi (+/-%)','GD khớp lệnh (KL)','GD khớp lệnh (GT)',
                                          'GD thỏa thuận (KL)','GD thỏa thuận (GT)','Giá mở cửa','Giá cao nhất','Giá thấp nhất'])
        return stock_info
    
    # function to scrape data dynamically
    def scrape_stock(self, driver, sleep_time=1):

        driver.get(self.__url)   # 

        if self.__start_date is None and self.__end_date is not None:
            date_entry2 = driver.find_element_by_id('ctl00_ContentPlaceHolder1_ctl03_dpkTradeDate2_txtDatePicker')
            date_entry2.send_keys(self.__end_date)
            search_button = driver.find_element_by_id('ctl00_ContentPlaceHolder1_ctl03_btSearch')
            driver.execute_script("arguments[0].click();", search_button)
            elem = WebDriverWait(driver, 10).until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            if elem:
                time.sleep(sleep_time)
                page_source = driver.page_source
                bs_source = BeautifulSoup(page_source, 'lxml')  # BeautifulSoup object for the page
            else:
                return "next page is not fully loaded"
        elif self.__start_date is not None and self.__end_date is None:
            date_entry1 = driver.find_element_by_id('ctl00_ContentPlaceHolder1_ctl03_dpkTradeDate1_txtDatePicker')
            date_entry1.send_keys(self.__start_date)
            search_button = driver.find_element_by_id('ctl00_ContentPlaceHolder1_ctl03_btSearch')
            driver.execute_script("arguments[0].click();", search_button)
            elem = WebDriverWait(driver, 10).until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            if elem:
                time.sleep(sleep_time)
                page_source = driver.page_source
                bs_source = BeautifulSoup(page_source, 'lxml')  # BeautifulSoup object for the page
            else:
                return 'next page is not fully loaded'

        elif self.__start_date is not None and self.__end_date is not None:
            date_entry1 = driver.find_element_by_id('ctl00_ContentPlaceHolder1_ctl03_dpkTradeDate1_txtDatePicker')
            date_entry1.send_keys(self.__start_date)
            date_entry2 = driver.find_element_by_id('ctl00_ContentPlaceHolder1_ctl03_dpkTradeDate2_txtDatePicker')
            date_entry2.send_keys(self.__end_date)
            search_button = driver.find_element_by_id('ctl00_ContentPlaceHolder1_ctl03_btSearch')
            driver.execute_script("arguments[0].click();", search_button)
            elem = WebDriverWait(driver, 10).until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            if elem:
                time.sleep(sleep_time)
                page_source = driver.page_source
                bs_source = BeautifulSoup(page_source, 'lxml')  # BeautifulSoup object for the page
            else:
                return 'next page is not fully loaded'

        else:
            page_source = driver.page_source
            bs_source = BeautifulSoup(page_source, 'lxml')  # BeautifulSoup object for the page


        data = self.__get_data(bs_source)
        size = data.shape[0]
        flag = True
        page_num='2'
        page_nums = bs_source.find('table', class_="CafeF_Paging").get_text().split()
        
        while flag:
            if page_num in page_nums:
                if (size % 2)==0:
                    form = "altitemTR"
                    last_date = bs_source.find('table',id="GirdTable2").find('tr', id="ctl00_ContentPlaceHolder1_ctl03_rptData2_ctl{}_{}".format(size, form)).find('td',class_="Item_DateItem").text
                else:
                    form = "itemTR"
                    last_date = bs_source.find('table',id="GirdTable2").find('tr', id="ctl00_ContentPlaceHolder1_ctl03_rptData2_ctl{}_{}".format(size, form)).find('td',class_="Item_DateItem").text
                
                link = driver.find_element_by_link_text(page_num)
                driver.execute_script("arguments[0].click();", link)
                #except:
                #    return page_num, page_nums, bs_source

                second_flag=True
                while second_flag:
                    page_source = driver.page_source
                    bs_source = BeautifulSoup(page_source, 'lxml')  # BeautifulSoup object for the page

                    date_time_str = bs_source.find('table',id="GirdTable2").find('tr', id="ctl00_ContentPlaceHolder1_ctl03_rptData2_ctl01_itemTR").find('td',class_="Item_DateItem").text
                    next_1st_date = datetime.datetime.strptime(date_time_str, '%d/%m/%Y')
                    prev_last_date = datetime.datetime.strptime(last_date, '%d/%m/%Y')
                    if next_1st_date <= prev_last_date:
                        second_flag=False
                #page_source = driver.page_source
                #data_source = driver.find_element_by_id('GirdTable2')
                #bs_source = BeautifulSoup(page_source, 'lxml')
                data_tmp = self.__get_data(bs_source)
                size = data_tmp.shape[0]
                data=data.append(data_tmp, ignore_index=True) 
                page_nums = bs_source.find('table', class_="CafeF_Paging").get_text().split()
                page_num = str(int(page_num)+1)
            else:
                flag=False
        self.__data = data
    
    # function to return scrapped data
    def get_scrapped_data(self):
        return self.__data

    # function to remove '\xa0'
    def remove_xa0(self):
        columns = self.__data.columns.values
        for col in columns:
            self.__data[col] = self.__data[col].str.replace('\xa0','')

    # function to return number of rows in data
    def get_nrows(self):
        return self.__data.shape[0]

## Class for Creating Dashboard of the Stock Scraped
class StockStat:

  # Constructor
  def __init__(self, data):
    self.__price = data
    self.__logReturn = np.log(data[:-1].values/data[1:].values)*100

  # get mean price
  def get_meanPrice(self):
    return round(np.mean(self.__price),2)
  # get variance of price
  def get_varPrice(self):
    return round(np.var(self.__price),2)
  # get standard deviation of price
  def get_stdPrice(self):
    return round(np.std(self.__price),2)
  # get the skewness of price:
  def get_skewPrice(self):
    return round(skew(self.__price),2)
  # get the kurtosis of price:
  def get_kurtPrice(self):
    return round(kurtosis(self.__price),2)
  
  # get mean of log returns
  def get_meanLogReturn(self):
    return round(np.mean(self.__logReturn),2)
  # get variance of log returns
  def get_varLogReturn(self):
    return round(np.var(self.__logReturn),2)
  # get standard deviation of log returns
  def get_stdLogReturn(self):
    return round(np.std(self.__logReturn),2)
  # get the skewness of price:
  def get_skewLogReturn(self):
    return round(skew(self.__logReturn),2)
  # get the kurtosis of price:
  def get_kurtLogReturn(self):
    return round(kurtosis(self.__logReturn),2)