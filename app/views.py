from django.shortcuts import render
from django.views.generic import View
from django.conf import settings
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from datetime import date
import requests
import json
import pandas as pd
import re
import time


# Instagram Graph API認証情報
def get_credentials():
    credentials = {}
    credentials['access_token'] = settings.ACCESS_TOKEN
    credentials['instagram_account_id'] = settings.INSTAGRAM_ACCOUNT_ID
    credentials['graph_domain'] = 'https://graph.facebook.com/'
    credentials['graph_version'] = 'v8.0'
    credentials['endpoint_base'] = credentials['graph_domain'] + credentials['graph_version'] + '/'
    return credentials


# Instagram Graph APIコール
def call_api(url, endpoint_params=''):
    # API送信
    if endpoint_params:
        data = requests.get(url, endpoint_params)
    else:
        data = requests.get(url)

    response = {}
    # API送信結果をjson形式で保存
    response['json_data'] = json.loads(data.content)
    return response


# ユーザーアカウント情報取得
def get_account_info(params):
    # エンドポイント
    # https://graph.facebook.com/{graph-api-version}/{ig-user-id}?fields={fields}&access_token={access-token}

    endpoint_params = {}
    # ユーザ名、プロフィール画像、フォロワー数、フォロー数、投稿数、メディア情報取得
    endpoint_params['fields'] = 'business_discovery.username(' + params['ig_username'] + '){username,profile_picture_url,follows_count,followers_count,media_count}'
    endpoint_params['access_token'] = params['access_token']
    url = params['endpoint_base'] + params['instagram_account_id']
    return call_api(url, endpoint_params)


# ページ送り
def get_pagenate_account_info(params):
    endpoint_params = {}
    endpoint_params['fields'] = 'business_discovery.username(' + params['ig_username'] + '){media.after(' + params['after_key'] + ').limit(1000){timestamp}}'
    endpoint_params['access_token'] = params['access_token']
    url = params['endpoint_base'] + params['instagram_account_id']
    return call_api(url, endpoint_params)


def search_account(url, keyword):
    options = Options()
    options.add_argument('--headless')  # バックグランドで実行
    options.add_argument('--no-sandbox')  # chrootで隔離された環境(Sandbox)での動作を無効
    # 共有メモリファイルの場所を/dev/shmから/tmpに移動
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    driver = webdriver.Chrome('/usr/local/bin/chromedriver', chrome_options=options)
    driver.get(url)

    input_element = driver.find_element_by_id('gsc-i-id1')
    input_element.clear()
    input_element.send_keys(keyword)
    input_element.send_keys(Keys.RETURN)
    time.sleep(2)

    return driver


def get_user_id(driver):
    '''
    ページからページネーションしながらURLを取得し、user_idを1つのリストにまとめる
    '''
    i = 2
    urls = []
    user_ids = []

    while True:
        # urlを収集
        url_objects = driver.find_elements_by_css_selector('div.gsc-thumbnail-inside > div > a')
        # もしurlのリストが存在するなら
        if url_objects:
            for object in url_objects:
                urls.append(object.get_attribute('href'))
        # urlのリストが存在しない場合->ページが終わった可能性あり
        else:
            print('URLが取得できませんでした。')
        try:
            urls.remove(None)
        except:
            pass

        # ページ送りを試す
        try:
            driver.find_element_by_xpath(f"//div[@id='___gcse_1']/div/div/div/div[5]/div[2]/div/div/div[2]/div/div[{i}]").click()
            print('次のページに行きます。')
            time.sleep(2)
        except:
            print('ページがなくなりました')
            break
        i += 1
        # アカウントのurlリストからuser_idの部分を取得　m.group(1)
    for text in urls:
        match = re.search(r'https://www.instagram.com/(.*?)/', text)
        if match:
            user_id = match.group(1)
            user_ids.append(user_id)
    user_ids = list(set(user_ids))

    return user_ids


class IndexView(View):
    def get(self, request, *args, **kwargs):
        keyword = 'タピオカ+淡路島'
        url = 'https://makitani.net/igusersearch/'
        media_count = 1000
        followers_count = 100
        this_year = 1

        driver = search_account(url, keyword)

        user_ids = get_user_id(driver)

        # Instagram Graph API認証情報取得
        params = get_credentials()

        user_list = []

        for user_id in user_ids:
            params['ig_username'] = user_id

            try:
                # アカウント情報取得
                account_response = get_account_info(params)
                business_discovery = account_response['json_data']['business_discovery']

                if business_discovery['media_count'] <= media_count and business_discovery['followers_count'] >= followers_count:
                    if this_year == 0:
                        user_list.append([
                            user_id,
                            business_discovery['profile_picture_url'],
                            business_discovery['followers_count'],
                            business_discovery['follows_count'],
                            business_discovery['media_count'],
                            'https://www.instagram.com/' + user_id
                        ])
                    else:
                        try:
                            after_key = business_discovery['media']['paging']['cursors']['after']
                        except KeyError:
                            after_key = []
                        params['after_key'] = after_key
                        pagenate_account_response = get_pagenate_account_info(params)
                        # ページ送り後の最後尾のタイムスタンプ取得
                        timestamp = pagenate_account_response['json_data']['business_discovery']['media']['data'][-1]['timestamp']
                        m = re.search('((\d{4})-\d{2}-\d{2}).*', timestamp)

                        # 最後のタイムスタンプから西暦m.group(2)を取得（文字列）
                        # もしも西暦が今年ならば
                        if m.group(2) == date.today().strftime('%Y'):
                            user_list.append([
                                user_id,
                                business_discovery['profile_picture_url'],
                                business_discovery['followers_count'],
                                business_discovery['follows_count'],
                                business_discovery['media_count'],
                                'https://www.instagram.com/' + user_id
                            ])
            except KeyError:
                pass

        # user_list = []
        # for i in range(2):
        #     user_list.append([
        #         'hathle',
        #         'https://placehold.jp/150x150.png',
        #         '111111',
        #         '2222',
        #         '233',
        #         'https://www.instagram.com/hathle/'
        #     ])
        user_data = pd.DataFrame(user_list, columns=[
            'username',
            'profile_picture_url',
            'followers_count',
            'follows_count',
            'media_count',
            'link'
        ])

        # フォロワー数で並び替え
        user_data = user_data.sort_values(['followers_count'], ascending=[False])

        return render(request, 'app/index.html', {
            'user_data': user_data,
            'keyword': keyword,
            'media_count': media_count,
            'followers_count': followers_count,
            'this_year': this_year
        })