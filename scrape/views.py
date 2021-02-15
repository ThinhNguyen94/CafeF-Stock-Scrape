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

def ScrapeInfo1(request):
    
    content = info_current.get_content()
    
    if request.method == 'GET':
        quote = request.GET.get('quote')
        sdate = request.GET.get('date_from')
        edate = request.GET.get('date_to')
        content['submitbutton'] = "Submit"
        content['keys'] = ['Ngày','Giá đóng cửa','Thay đổi (+/-%)','GD khớp lệnh (KL)','GD khớp lệnh (GT)',
        'GD thỏa thuận (KL)','GD thỏa thuận (GT)','Giá mở cửa','Giá cao nhất','Giá thấp nhất']
        content['data'] = data_test
        content['quote'] = quote
        content['sdate'] = sdate
        content['edate'] = edate
        content['nrows'] = len(data_test['Ngày'])

        # dump data
        dataJSON = dumps(content)
        content['dataJSON'] = dataJSON

        info_current.set_content(content) # store current content
    
    return render(request, 'scrape/home.html', content)

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
        #content['numPageView'] = numPageView
        #content['numPageView_1'] = numPageView+1

        # dump data
        dataJSON = dumps(content)
        content['dataJSON'] = dataJSON

        info_current.set_content(content) # store current content
    
    return render(request, 'scrape/home.html', content)

# Return summary statistics of the stock
def Summary_stat(request):
    content = info_current.get_content()
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

# Return info dashboard view on the dashboard page 
def Dashboard(request):
	content = {}
	return render(request, 'scrape/dashboard.html', content)

# Show info about authors and application 
def AboutPage(request):
    content = {}
    return render(request, 'scrape/about.html', content)


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

###------------------------------------------------------TEST DATA-------------------------------------------------------###
# test data
data_test = {'Ngày': ['22/01/2021',
  '21/01/2021',
  '20/01/2021',
  '19/01/2021',
  '18/01/2021',
  '15/01/2021',
  '14/01/2021',
  '13/01/2021',
  '12/01/2021',
  '11/01/2021',
  '08/01/2021',
  '07/01/2021',
  '06/01/2021',
  '05/01/2021',
  '04/01/2021',
  '31/12/2020',
  '30/12/2020',
  '29/12/2020',
  '28/12/2020',
  '25/12/2020',
  '24/12/2020',
  '23/12/2020',
  '22/12/2020',
  '21/12/2020',
  '18/12/2020',
  '17/12/2020',
  '16/12/2020',
  '15/12/2020',
  '14/12/2020',
  '11/12/2020',
  '10/12/2020'],
 'Giá đóng cửa': ['1,166.78\xa0',
  '1,164.21\xa0',
  '1,134.68\xa0',
  '1,131.00\xa0',
  '1,191.94\xa0',
  '1,194.20\xa0',
  '1,187.40\xa0',
  '1,186.05\xa0',
  '1,192.28\xa0',
  '1,184.89\xa0',
  '1,167.69\xa0',
  '1,156.49\xa0',
  '1,143.21\xa0',
  '1,132.55\xa0',
  '1,120.47\xa0',
  '1,103.87\xa0',
  '1,097.54\xa0',
  '1,099.49\xa0',
  '1,091.33\xa0',
  '1,084.42\xa0',
  '1,067.52\xa0',
  '1,078.90\xa0',
  '1,083.45\xa0',
  '1,081.08\xa0',
  '1,067.46\xa0',
  '1,051.77\xa0',
  '1,066.99\xa0',
  '1,055.27\xa0',
  '1,064.09\xa0',
  '1,045.96\xa0',
  '1,030.91\xa0'],
 'Thay đổi (+/-%)': ['2.57 (0.22 %)',
  '29.53 (2.60 %)',
  '3.68 (0.33 %)',
  '-60.94 (-5.11 %)',
  '-2.26 (-0.19 %)',
  '6.80 (0.57 %)',
  '1.35 (0.11 %)',
  '-6.23 (-0.52 %)',
  '7.39 (0.62 %)',
  '17.20 (1.47 %)',
  '11.20 (0.97 %)',
  '13.28 (1.16 %)',
  '10.66 (0.94 %)',
  '12.08 (1.08 %)',
  '16.60 (1.50 %)',
  '6.33 (0.58 %)',
  '-1.95 (-0.18 %)',
  '8.16 (0.75 %)',
  '23.81 (2.23 %)',
  '16.90 (1.58 %)',
  '-11.38 (-1.05 %)',
  '-4.55 (-0.42 %)',
  '2.37 (0.22 %)',
  '13.62 (1.28 %)',
  '15.69 (1.49 %)',
  '-15.22 (-1.43 %)',
  '11.72 (1.11 %)',
  '-8.82 (-0.83 %)',
  '18.13 (1.73 %)',
  '15.05 (1.46 %)',
  '-8.22 (-0.79 %)'],
 'GD khớp lệnh (KL)': ['689,503,400\xa0',
  '636,293,700\xa0',
  '768,338,900\xa0',
  '886,850,500\xa0',
  '676,078,200\xa0',
  '713,128,700\xa0',
  '707,685,900\xa0',
  '707,397,200\xa0',
  '641,960,400\xa0',
  '735,459,400\xa0',
  '724,072,400\xa0',
  '683,626,300\xa0',
  '685,752,700\xa0',
  '672,525,100\xa0',
  '669,130,300\xa0',
  '472,642,020\xa0',
  '587,368,160\xa0',
  '585,681,180\xa0',
  '634,183,550\xa0',
  '564,081,800\xa0',
  '658,279,720\xa0',
  '711,447,510\xa0',
  '661,706,010\xa0',
  '626,766,500\xa0',
  '526,524,670\xa0',
  '596,966,690\xa0',
  '530,251,460\xa0',
  '579,155,230\xa0',
  '471,507,860\xa0',
  '387,847,600\xa0',
  '520,204,600\xa0'],
 'GD khớp lệnh (GT)': ['14,546,189,000,000\xa0',
  '13,880,948,600,000\xa0',
  '16,334,832,930,000\xa0',
  '17,812,826,360,000\xa0',
  '15,825,820,020,000\xa0',
  '16,136,444,860,000\xa0',
  '15,191,805,570,000\xa0',
  '15,439,975,540,000\xa0',
  '14,595,104,490,000\xa0',
  '16,230,220,770,000\xa0',
  '16,021,994,130,000\xa0',
  '15,176,802,660,000\xa0',
  '15,741,527,590,000\xa0',
  '14,661,104,720,000\xa0',
  '14,623,112,250,000\xa0',
  '9,919,370,000,000\xa0',
  '11,771,211,000,000\xa0',
  '12,592,777,000,000\xa0',
  '12,836,673,000,000\xa0',
  '11,293,439,780,000\xa0',
  '12,911,061,230,000\xa0',
  '13,502,241,180,000\xa0',
  '12,732,483,000,000\xa0',
  '12,975,784,000,000\xa0',
  '11,651,496,000,000\xa0',
  '13,524,118,260,000\xa0',
  '10,864,766,000,000\xa0',
  '12,170,625,000,000\xa0',
  '10,338,291,000,000\xa0',
  '8,676,369,820,000\xa0',
  '11,459,379,000,000\xa0'],
 'GD thỏa thuận (KL)': ['19,227,769\xa0',
  '37,484,459\xa0',
  '21,384,403\xa0',
  '55,759,306\xa0',
  '20,821,248\xa0',
  '33,684,488\xa0',
  '36,988,696\xa0',
  '56,524,702\xa0',
  '21,482,869\xa0',
  '54,893,671\xa0',
  '37,886,848\xa0',
  '34,832,636\xa0',
  '60,632,848\xa0',
  '48,776,542\xa0',
  '46,606,545\xa0',
  '21,892,568\xa0',
  '52,881,165\xa0',
  '57,183,047\xa0',
  '51,250,542\xa0',
  '59,430,404\xa0',
  '68,652,918\xa0',
  '67,324,990\xa0',
  '57,180,437\xa0',
  '43,857,383\xa0',
  '52,812,573\xa0',
  '25,666,998\xa0',
  '26,586,761\xa0',
  '38,939,220\xa0',
  '60,713,038\xa0',
  '35,023,027\xa0',
  '49,060,107\xa0'],
 'GD thỏa thuận (GT)': ['868,840,361,130\xa0',
  '1,286,066,789,800\xa0',
  '876,463,802,750\xa0',
  '2,162,189,354,400\xa0',
  '780,722,619,900\xa0',
  '2,276,411,532,200\xa0',
  '1,611,035,047,480\xa0',
  '2,097,366,817,880\xa0',
  '671,339,678,450\xa0',
  '1,815,311,306,920\xa0',
  '1,482,412,502,000\xa0',
  '1,208,772,510,800\xa0',
  '1,912,320,839,900\xa0',
  '1,206,825,283,580\xa0',
  '1,299,730,157,350\xa0',
  '613,681,705,780\xa0',
  '1,384,248,426,120\xa0',
  '1,588,759,922,010\xa0',
  '1,413,570,527,080\xa0',
  '1,407,956,145,100\xa0',
  '1,097,867,980,500\xa0',
  '1,257,813,122,660\xa0',
  '1,654,108,948,620\xa0',
  '1,038,990,766,200\xa0',
  '1,244,704,251,350\xa0',
  '687,578,071,300\xa0',
  '729,734,433,000\xa0',
  '978,862,006,400\xa0',
  '1,891,557,607,530\xa0',
  '1,517,419,327,700\xa0',
  '1,490,818,881,400\xa0'],
 'Giá mở cửa': ['1,166.77\xa0',
  '1,146.86\xa0',
  '1,136.50\xa0',
  '1,189.91\xa0',
  '1,198.79\xa0',
  '1,188.84\xa0',
  '1,189.48\xa0',
  '1,197.32\xa0',
  '1,190.38\xa0',
  '1,176.47\xa0',
  '1,164.10\xa0',
  '1,147.26\xa0',
  '1,139.12\xa0',
  '1,116.96\xa0',
  '1,113.77\xa0',
  '1,098.25\xa0',
  '1,099.78\xa0',
  '1,090.49\xa0',
  '1,094.37\xa0',
  '1,068.83\xa0',
  '1,083.83\xa0',
  '1,087.89\xa0',
  '1,081.85\xa0',
  '1,071.62\xa0',
  '1,055.75\xa0',
  '1,065.85\xa0',
  '1,058.34\xa0',
  '1,062.02\xa0',
  '1,048.97\xa0',
  '1,033.19\xa0',
  '1,041.65\xa0'],
 'Giá cao nhất': ['1,175.72\xa0',
  '1,164.21\xa0',
  '1,142.48\xa0',
  '1,191.94\xa0',
  '1,200.85\xa0',
  '1,197.74\xa0',
  '1,190.50\xa0',
  '1,200.82\xa0',
  '1,192.28\xa0',
  '1,186.45\xa0',
  '1,176.33\xa0',
  '1,156.49\xa0',
  '1,152.85\xa0',
  '1,133.16\xa0',
  '1,126.43\xa0',
  '1,105.33\xa0',
  '1,108.83\xa0',
  '1,102.79\xa0',
  '1,096.11\xa0',
  '1,084.42\xa0',
  '1,084.76\xa0',
  '1,094.09\xa0',
  '1,084.23\xa0',
  '1,081.60\xa0',
  '1,068.56\xa0',
  '1,066.99\xa0',
  '1,066.99\xa0',
  '1,067.45\xa0',
  '1,064.09\xa0',
  '1,045.96\xa0',
  '1,044.10\xa0'],
 'Giá thấp nhất': ['1,161.43\xa0',
  '1,132.66\xa0',
  '1,098.05\xa0',
  '1,117.17\xa0',
  '1,190.33\xa0',
  '1,188.84\xa0',
  '1,178.84\xa0',
  '1,183.18\xa0',
  '1,179.24\xa0',
  '1,175.00\xa0',
  '1,160.48\xa0',
  '1,143.44\xa0',
  '1,133.70\xa0',
  '1,116.49\xa0',
  '1,113.59\xa0',
  '1,096.27\xa0',
  '1,094.91\xa0',
  '1,087.93\xa0',
  '1,083.90\xa0',
  '1,061.83\xa0',
  '1,046.89\xa0',
  '1,077.92\xa0',
  '1,077.06\xa0',
  '1,067.46\xa0',
  '1,051.77\xa0',
  '1,051.42\xa0',
  '1,055.27\xa0',
  '1,052.01\xa0',
  '1,045.96\xa0',
  '1,030.06\xa0',
  '1,030.91\xa0']}