#   - [1.30]: [同一环境变量获取]
#   - [2.0]:  [API域名迁移 caiyun.feixin.10086.cn → m.mcloud.139.com]
#             [SSO接口迁移 orches.yun.139.com → user-njs.yun.139.com / m.mcloud.139.com]
#             [JWT登录迁移 caiyun.feixin.10086.cn:7071 → m.mcloud.139.com/ycloud/auth-service]
#             [签到接口 info→infoV3, receive→receiveV2, 新增startSignIn/doTaskPost]
#             [任务列表 taskList→taskListV2(group模式)]
#             [修复fruitLogin Cookie提取逻辑]
# 注: 本脚本仅用于个人学习和交流，请勿用于非法用途。作者不承担由于滥用此脚本所引起的任何责任，请在下载后24小时内删除。
# new Env("移动云盘")
# 作者: 洋洋不瘦
# 原始 fix 20240828 ArcadiaScriptPublic  频道：https://t.me/ArcadiaScript 群组：https://t.me/ArcadiaScriptPublic
# API迁移修复 20260517
# 抓包 第一个参数小程序orches.yun.139.com 或者aas.caiyun.feixin.10086.cn 搜Basic 全局搜也行  第三个参数app 域名caiyun.feixin.10086.cn或者签到链接https://caiyun.feixin.10086.cn:7071/market/signin/task/click?key=task&id=409的jwttoken
import os
import random
import re
import time
from os import path

import requests

ua = 'Mozilla/5.0 (Linux; Android 11; M2012K10C Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/90.0.4430.210 Mobile Safari/537.36 MCloudApp/12.6.0'

err_accounts = ''  # 异常账号
err_message = ''  # 错误信息
user_amount = ''  # 用户云朵·数量
GLOBAL_DEBUG = False

# ===================== 新旧域名配置 =====================
# 旧域名(已404): caiyun.feixin.10086.cn / caiyun.feixin.10086.cn:7071
# 新域名: m.mcloud.139.com
OLD_MARKET_BASE = 'https://caiyun.feixin.10086.cn'       # 已废弃
NEW_MARKET_BASE = 'https://m.mcloud.139.com'              # 新市场API域名
OLD_AUTH_BASE = 'https://caiyun.feixin.10086.cn:7071'     # 已废弃
NEW_AUTH_BASE = 'https://m.mcloud.139.com'                # 新认证API域名
SSO_URL = 'https://orches.yun.139.com/orchestration/auth-rebuild/token/v1.0/querySpecToken'  # SSO仍可用
NEW_SSO_URL = 'https://user-njs.yun.139.com/user/querySpecTokenV2'  # 新SSO(加密)
MLOUD_SSO_URL = 'https://m.mcloud.139.com/ycloud/api/cloud/userdomain/v2/querySpecToken'  # mcloud内SSO


# 发送通知
def load_send():
    cur_path = path.abspath(path.dirname(__file__))
    notify_file = cur_path + "/notify.py"

    if path.exists(notify_file):
        try:
            from notify import send  # 导入模块的send为notify_send
            print("加载通知服务成功！")
            return send  # 返回导入的函数
        except ImportError:
            print("加载通知服务失败~")
    else:
        print("加载通知服务失败~")

    return False  # 返回False表示未成功加载通知服务


class YP:
    def __init__(self, cookie):
        self.notebook_id = None
        self.note_token = None
        self.note_auth = None
        self.click_num = 15  # 定义抽奖次数和摇一摇戳一戳次数
        self.draw = 1  # 抽奖次数，首次免费
        self.session = requests.Session()

        self.timestamp = str(int(round(time.time() * 1000)))
        self.cookies = {'sensors_stay_time': self.timestamp}
        self.Authorization = cookie.split("#")[0]
        self.account = cookie.split("#")[1]
        self.auth_token = cookie.split("#")[2]
        self.encrypt_account = self.account[:3] + "*" * 4 + self.account[7:]
        self.device_id = self._generate_device_id()  # 依赖account和timestamp，需在它们之后调用
        self.fruit_url = 'https://happy.mail.10086.cn/jsp/cn/garden/'

        self.jwtHeaders = {
            'User-Agent': ua,
            'Accept': '*/*',
            'Host': 'm.mcloud.139.com',
        }
        self.treeHeaders = {
            'Host': 'happy.mail.10086.cn',
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': ua,
            'Referer': 'https://happy.mail.10086.cn/jsp/cn/garden/wap/index.html?sourceid=1003',
            'Cookie': '',
        }

    def _generate_device_id(self):
        """生成deviceId，新API(startSignIn/doTaskPost)需要此字段"""
        import hashlib
        raw = f'{self.account}{self.timestamp}{random.randint(100000, 999999)}'
        return hashlib.md5(raw.encode()).hexdigest().upper()

    # 捕获异常
    @staticmethod
    def catch_errors(func):
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                global err_message
                print("错误:", str(e))
                err_message += f'用户[{self.encrypt_account}]:{e}\n'  # 错误信息
            return None

        return wrapper

    @catch_errors
    def run(self):
        if self.jwt():
            self.signin_status()
            self.click()
            # 任务
            self.get_tasklist(url='sign_in_3', app_type='cloud_app')
            print(f'\n☁️ 云朵大作战')
            self.cloud_game()
            print(f'\n🌳 果园任务')
            self.fruitLogin()
            print(f'\n📰 公众号任务')
            self.wxsign()
            self.shake()
            self.surplus_num()
            print(f'\n🔥 热门任务')
            self.backup_cloud()
            self.open_send()
            print(f'\n📧 139邮箱任务')
            self.get_tasklist(url='sign_in_3', app_type='email_app')
            self.receive()
        else:
            global err_accounts
            # 失效账号
            err_accounts += f'{self.encrypt_account}\n'

    def send_request(self, url, headers=None, cookies=None, data=None, params=None, method='GET', debug=None,
                     retries=5):

        debug = debug if debug is not None else GLOBAL_DEBUG

        self.session.headers.update(headers or {})
        if cookies:
            self.session.cookies.update(cookies)
        request_args = {'json': data} if isinstance(data, dict) else {'data': data}

        for attempt in range(retries):
            try:
                response = self.session.request(method, url, params=params, **request_args)
                response.raise_for_status()
                if debug:
                    print(f'\n【{url}】响应数据:\n{response.text}')
                return response
            except (requests.RequestException, ConnectionError, TimeoutError) as e:
                print(f"请求异常: {e}")
                if attempt >= retries - 1:
                    print("达到最大重试次数。")
                    return None
                time.sleep(1)

    # 随机延迟默认1-1.5s
    def sleep(self, min_delay=1, max_delay=1.5):
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

    # 日志
    def log_info(self, err_msg=None, amount=None):
        global err_message, user_amount
        if err_msg is not None:
            err_message += f'用户[{self.encrypt_account}]:{err_msg}\n'  # 错误信息
        elif amount is not None:
            user_amount += f'用户[{self.encrypt_account}]:{amount}\n'  # 云朵数量

    # 刷新令牌(SSO) — 旧接口仍可用
    def sso(self):
        sso_url = SSO_URL
        sso_headers = {
            'Authorization': self.Authorization,
            'User-Agent': ua,
            'Content-Type': 'application/json',
            'Accept': '*/*',
            'Host': 'orches.yun.139.com'
        }
        sso_payload = {"account": self.account, "toSourceId": "001005"}
        resp = self.send_request(sso_url, headers=sso_headers, data=sso_payload, method='POST')
        if resp is None:
            return None
        sso_data = resp.json()

        if sso_data.get('success'):
            refresh_token = sso_data['data']['token']
            return refresh_token
        else:
            print(sso_data.get('message', 'SSO失败'))
            return None

    # jwt — 使用新域名认证
    def jwt(self):
        # 获取jwttoken
        token = self.sso()
        if token is not None:
            # 新JWT登录接口: m.mcloud.139.com/ycloud/auth-service/auth/tyrzLogin
            jwt_url = f"{NEW_AUTH_BASE}/ycloud/auth-service/auth/tyrzLogin"
            jwt_payload = {
                "token": token,
                "openAccount": 0,
                "marketName": "sign_in_3",
                "sourceId": "1002"
            }
            jwt_headers = {
                'User-Agent': ua,
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'Host': 'm.mcloud.139.com',
                'Origin': 'https://m.mcloud.139.com',
                'Referer': 'https://m.mcloud.139.com/portal/mobilecloud/index.html',
            }
            resp = self.send_request(jwt_url, headers=jwt_headers, data=jwt_payload, method='POST')
            if resp is None:
                print('-jwt请求失败')
                return False
            jwt_data = resp.json()
            if jwt_data.get('code') != 0:
                print(jwt_data.get('msg', 'jwt失败'))
                return False
            jwt_token = jwt_data['result']['token']
            self.jwtHeaders['jwtToken'] = jwt_token
            self.cookies['jwtToken'] = jwt_token
            return True
        else:
            print('-ck可能失效了')
            return False

    # 签到查询与执行 — 使用新API(infoV3 + startSignIn + doTaskPost)
    @catch_errors
    def signin_status(self):
        self.sleep()
        # 查询签到状态: infoV3
        check_url = f'{NEW_MARKET_BASE}/market/signin/page/infoV3?client=app'
        check_resp = self.send_request(check_url, headers=self.jwtHeaders, cookies=self.cookies)
        if check_resp is None:
            print('❌ 签到查询请求失败')
            return
        check_data = check_resp.json()
        if check_data.get('msg') == 'success':
            today_sign_in = check_data.get('result', {}).get('todaySignIn', False)

            if today_sign_in:
                print('✅已签到')
            else:
                print('❌ 未签到，开始执行签到...')
                # 执行签到: startSignIn
                signin_url = f'{NEW_MARKET_BASE}/market/signin/page/startSignIn?client=app'
                signin_resp = self.send_request(signin_url, headers=self.jwtHeaders, cookies=self.cookies)
                if signin_resp is None:
                    print('❌ 签到请求失败')
                    return
                signin_data = signin_resp.json()
                if signin_data.get('code') == 0:
                    sign_points = signin_data.get('result', {}).get('signInPoints', 0)
                    print(f'✅签到成功，获得{sign_points}云朵')
                else:
                    print(f'签到响应: {signin_data.get("msg", "未知错误")}')
                    self.log_info(signin_data.get('msg'))

                # 领取签到云朵: doTaskPost
                self.sleep()
                dotask_url = f'{NEW_MARKET_BASE}/market/signin/page/doTaskPost'
                dotask_payload = {
                    "client": "app",
                    "deviceId": self.device_id
                }
                dotask_resp = self.send_request(dotask_url, headers=self.jwtHeaders, cookies=self.cookies,
                                                data=dotask_payload, method='POST')
                if dotask_resp and dotask_resp.json().get('code') == 0:
                    print('✅签到云朵领取成功')
                else:
                    print('❌签到云朵领取失败')
        else:
            print(check_data.get('msg', '签到查询失败'))
            self.log_info(check_data.get('msg'))

    # 戳一下 — 新域名
    def click(self):
        url = f"{NEW_MARKET_BASE}/market/signin/task/click?key=task&id=319"
        successful_click = 0  # 获得次数

        try:
            for _ in range(self.click_num):
                return_data = self.send_request(url, headers=self.jwtHeaders, cookies=self.cookies)
                if return_data is None:
                    continue
                data = return_data.json()
                time.sleep(0.2)

                if 'result' in data:
                    print(f'✅{data["result"]}')
                    successful_click += 1

            if successful_click == 0:
                print(f'❌未获得 x {self.click_num}')
        except Exception as e:
            print(f'错误信息:{e}')

    # 刷新笔记token
    @catch_errors
    def refresh_notetoken(self):
        note_url = 'http://mnote.caiyun.feixin.10086.cn/noteServer/api/authTokenRefresh.do'
        note_payload = {
            "authToken": self.auth_token,
            "userPhone": self.account
        }
        note_headers = {
            'X-Tingyun-Id': 'p35OnrDoP8k;c=2;r=1122634489;u=43ee994e8c3a6057970124db00b2442c::8B3D3F05462B6E4C',
            'Charset': 'UTF-8',
            'Connection': 'Keep-Alive',
            'User-Agent': 'mobile',
            'APP_CP': 'android',
            'CP_VERSION': '3.2.0',
            'x-huawei-channelsrc': '10001400',
            'Host': 'mnote.caiyun.feixin.10086.cn',
            'Content-Type': 'application/json; charset=UTF-8',
            'Accept-Encoding': 'gzip'
        }

        try:
            response = self.send_request(note_url, headers=note_headers, data=note_payload, method="POST")
            if response is None:
                return
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print('出错了:', e)
            return

        self.note_token = response.headers.get('NOTE_TOKEN')
        self.note_auth = response.headers.get('APP_AUTH')

    # 任务列表 — 使用taskListV2(group模式)
    def get_tasklist(self, url, app_type):
        # 新接口: taskListV2，按group分批查询
        groups = ['day', 'month']  # 主要关心的任务分组
        task_list = {}

        for group in groups:
            task_url = f'{NEW_MARKET_BASE}/market/signin/task/taskListV2?marketname={url}&clientVersion=12.6.0&group={group}'
            resp = self.send_request(task_url, headers=self.jwtHeaders, cookies=self.cookies)
            if resp is None:
                continue
            resp_data = resp.json()
            if resp_data.get('code') == 0:
                result = resp_data.get('result', {})
                # taskListV2返回格式: {"result": {"day": [...], "month": [...]}}
                for g, tasks in result.items():
                    if isinstance(tasks, list):
                        task_list[g] = tasks
            self.sleep()

        # 任务列表处理
        try:
            for task_type, tasks in task_list.items():
                if app_type == 'cloud_app':
                    if task_type == "month":
                        print('\n📆 云盘每月任务')
                        for month in tasks:
                            task_id = month.get('id')
                            if task_id in [110, 113, 417, 409]:
                                continue
                            task_name = month.get('name', '')
                            # 去除HTML标签
                            task_name = re.sub(r'<[^>]+>', '', task_name)
                            task_status = month.get('state', '')

                            if task_status == 'FINISH':
                                print(f'-已完成: {task_name}')
                                continue
                            print(f'-去完成: {task_name}')
                            self.do_task(task_id, task_type='month', app_type='cloud_app')
                            time.sleep(2)
                    elif task_type == "day":
                        print('\n📆 云盘每日任务')
                        for day in tasks:
                            task_id = day.get('id')
                            if task_id == 404:
                                continue
                            task_name = day.get('name', '')
                            task_name = re.sub(r'<[^>]+>', '', task_name)
                            task_status = day.get('state', '')

                            if task_status == 'FINISH':
                                print(f'-已完成: {task_name}')
                                continue
                            print(f'-去完成: {task_name}')
                            self.do_task(task_id, task_type='day', app_type='cloud_app')
                elif app_type == 'email_app':
                    if task_type == "month":
                        print('\n📆 139邮箱每月任务')
                        for month in tasks:
                            task_id = month.get('id')
                            task_name = month.get('name', '')
                            task_name = re.sub(r'<[^>]+>', '', task_name)
                            task_status = month.get('state', '')
                            if task_id in [1004, 1005, 1015, 1020]:
                                continue

                            if task_status == 'FINISH':
                                print(f'-已完成: {task_name}')
                                continue
                            print(f'-去完成: {task_name}')
                            self.do_task(task_id, task_type='month', app_type='email_app')
                            time.sleep(2)
                    elif task_type == "day":
                        print('\n📆 139邮箱每日任务')
                        for day in tasks:
                            task_id = day.get('id')
                            task_name = day.get('name', '')
                            task_name = re.sub(r'<[^>]+>', '', task_name)
                            task_status = day.get('state', '')

                            if task_status == 'FINISH':
                                print(f'-已完成: {task_name}')
                                continue
                            print(f'-去完成: {task_name}')
                            self.do_task(task_id, task_type='day', app_type='email_app')
        except Exception as e:
            print(f'错误信息:{e}')

    # 做任务
    @catch_errors
    def do_task(self, task_id, task_type, app_type):
        self.sleep()
        task_url = f'{NEW_MARKET_BASE}/market/signin/task/click?key=task&id={task_id}'
        self.send_request(task_url, headers=self.jwtHeaders, cookies=self.cookies)

        if app_type == 'cloud_app':
            if task_type == 'day':
                if task_id == 106:
                    print('-开始上传文件，默认0kb')
                    self.updata_file()
                elif task_id == 107:
                    self.refresh_notetoken()
                    print('-获取默认笔记id')
                    note_url = 'http://mnote.caiyun.feixin.10086.cn/noteServer/api/syncNotebookV3.do'
                    headers = {
                        'X-Tingyun-Id': 'p35OnrDoP8k;c=2;r=1122634489;u=43ee994e8c3a6057970124db00b2442c::8B3D3F05462B6E4C',
                        'Charset': 'UTF-8',
                        'Connection': 'Keep-Alive',
                        'User-Agent': 'mobile',
                        'APP_CP': 'android',
                        'CP_VERSION': '3.2.0',
                        'x-huawei-channelsrc': '10001400',
                        'APP_NUMBER': self.account,
                        'APP_AUTH': self.note_auth,
                        'NOTE_TOKEN': self.note_token,
                        'Host': 'mnote.caiyun.feixin.10086.cn',
                        'Content-Type': 'application/json; charset=UTF-8',
                        'Accept': '*/*'
                    }
                    payload = {
                        "addNotebooks": [],
                        "delNotebooks": [],
                        "notebookRefs": [],
                        "updateNotebooks": []
                    }
                    return_data = self.send_request(url=note_url, headers=headers, data=payload,
                                                    method='POST')
                    if return_data is None:
                        return print('出错了')
                    rd = return_data.json()
                    self.notebook_id = rd['notebooks'][0]['notebookId']
                    print('开始创建笔记')
                    self.create_note(headers)
            elif task_type == 'month':
                pass
        elif app_type == 'email_app':
            if task_type == 'month':
                pass

    # 上传文件
    @catch_errors
    def updata_file(self):
        url = 'http://ose.caiyun.feixin.10086.cn/richlifeApp/devapp/IUploadAndDownload'
        headers = {
            'x-huawei-uploadSrc': '1',
            'x-ClientOprType': '11',
            'Connection': 'keep-alive',
            'x-NetType': '6',
            'x-DeviceInfo': '6|127.0.0.1|1|10.0.1|Xiaomi|M2012K10C|CB63218727431865A48E691BFFDB49A1|02-00-00-00-00-00|android 11|1080X2272|zh||||032|',
            'x-huawei-channelSrc': '10000023',
            'x-MM-Source': '032',
            'x-SvcType': '1',
            'APP_NUMBER': self.account,
            'Authorization': self.Authorization,
            'X-Tingyun-Id': 'p35OnrDoP8k;c=2;r=1955442920;u=43ee994e8c3a6057970124db00b2442c::8B3D3F05462B6E4C',
            'Host': 'ose.caiyun.feixin.10086.cn',
            'User-Agent': 'okhttp/3.11.0',
            'Content-Type': 'application/xml; charset=UTF-8',
            'Accept': '*/*'
        }
        payload = '''
                                <pcUploadFileRequest>
                                    <ownerMSISDN>{phone}</ownerMSISDN>
                                    <fileCount>1</fileCount>
                                    <totalSize>1</totalSize>
                                    <uploadContentList length="1">
                                        <uploadContentInfo>
                                            <comlexFlag>0</comlexFlag>
                                            <contentDesc><![CDATA[]]></contentDesc>
                                            <contentName><![CDATA[000000.txt]]></contentName>
                                            <contentSize>1</contentSize>
                                            <contentTAGList></contentTAGList>
                                            <digest>C4CA4238A0B923820DCC509A6F75849B</digest>
                                            <exif/>
                                            <fileEtag>0</fileEtag>
                                            <fileVersion>0</fileVersion>
                                            <updateContentID></updateContentID>
                                        </uploadContentInfo>
                                    </uploadContentList>
                                    <newCatalogName></newCatalogName>
                                    <parentCatalogID></parentCatalogID>
                                    <operation>0</operation>
                                    <path></path>
                                    <manualRename>2</manualRename>
                                    <autoCreatePath length="0"/>
                                    <tagID></tagID>
                                    <tagType></tagType>
                                </pcUploadFileRequest>
                            '''.format(phone=self.account)

        response = requests.post(url=url, headers=headers, data=payload)
        if response is None:
            return
        if response.status_code != 200:
            return print('-上传失败')
        print('-上传文件成功')

    # 创建笔记
    def create_note(self, headers):
        note_id = self.get_note_id(32)  # 获取随机笔记id
        createtime = str(int(round(time.time() * 1000)))
        time.sleep(3)
        updatetime = str(int(round(time.time() * 1000)))
        note_url = 'http://mnote.caiyun.feixin.10086.cn/noteServer/api/createNote.do'
        payload = {
            "archived": 0,
            "attachmentdir": note_id,
            "attachmentdirid": "",
            "attachments": [],
            "audioInfo": {
                "audioDuration": 0,
                "audioSize": 0,
                "audioStatus": 0
            },
            "contentid": "",
            "contents": [{
                "contentid": 0,
                "data": "<font size=\"3\">000000</font>",
                "noteId": note_id,
                "sortOrder": 0,
                "type": "RICHTEXT"
            }],
            "cp": "",
            "createtime": createtime,
            "description": "android",
            "expands": {
                "noteType": 0
            },
            "latlng": "",
            "location": "",
            "noteid": note_id,
            "notestatus": 0,
            "remindtime": "",
            "remindtype": 1,
            "revision": "1",
            "sharecount": "0",
            "sharestatus": "0",
            "system": "mobile",
            "tags": [{
                "id": self.notebook_id,
                "orderIndex": "0",
                "text": "默认笔记本"
            }],
            "title": "00000",
            "topmost": "0",
            "updatetime": updatetime,
            "userphone": self.account,
            "version": "1.00",
            "visitTime": ""
        }
        create_note_data = self.send_request(note_url, headers=headers, data=payload, method="POST")
        if create_note_data and create_note_data.status_code == 200:
            print('-创建笔记成功')
        else:
            print('-创建失败')

    # 笔记id
    def get_note_id(self, length):
        characters = '19f3a063d67e4694ca63a4227ec9a94a19088404f9a28084e3e486b928039a299bf756ebc77aa4f6bfa250308ec6a8be8b63b5271a00350d136d117b8a72f39c5bd15cdfd350cba4271dc797f15412d9f269e666aea5039f5049d00739b320bb9e8585a008b52c1cbd86970cae9476446f3e41871de8d9f6112db94b05e5dc7ea0a942a9daf145ac8e487d3d5cba7cea145680efc64794d43dd15c5062b81e1cda7bf278b9bc4e1b8955846e6bc4b6a61c28f831f81b2270289e5a8a677c3141ddc9868129060c0c3b5ef507fbd46c004f6de346332ef7f05c0094215eae1217ee7c13c8dca6d174cfb49c716dd42903bb4b02d823b5f1ff93c3f88768251b56cc'
        note_id = ''.join(random.choice(characters) for _ in range(length))
        return note_id

    # 公众号签到 — 新域名
    @catch_errors
    def wxsign(self):
        self.sleep()
        url = f'{NEW_MARKET_BASE}/market/playoffic/followSignInfo?isWx=true'
        return_data = self.send_request(url, headers=self.jwtHeaders, cookies=self.cookies)
        if return_data is None:
            print('❌公众号签到请求失败')
            return
        rd = return_data.json()

        if rd.get('msg') != 'success':
            return print(rd.get('msg', '请求失败'))
        if not rd.get('result', {}).get('todaySignIn'):
            return print('❌签到失败,可能未绑定公众号')
        return print('✅签到成功')

    # 摇一摇 — 新域名
    def shake(self):
        url = f"{NEW_MARKET_BASE}/market/shake-server/shake/shakeIt?flag=1"
        successful_shakes = 0  # 记录成功摇中的次数

        try:
            for _ in range(self.click_num):
                return_data = self.send_request(url=url, cookies=self.cookies, headers=self.jwtHeaders,
                                                method='POST')
                if return_data is None:
                    continue
                rd = return_data.json()
                time.sleep(1)
                shake_prize_config = rd.get("result", {}).get("shakePrizeconfig")

                if shake_prize_config:
                    print(f"🎉摇一摇获得: {shake_prize_config['name']}")
                    successful_shakes += 1
        except Exception as e:
            print(f'错误信息: {e}')
        if successful_shakes == 0:
            print(f'❌未摇中 x {self.click_num}')

    # 查询剩余抽奖次数 — 新域名
    @catch_errors
    def surplus_num(self):
        self.sleep()
        draw_info_url = f'{NEW_MARKET_BASE}/market/playoffic/drawInfo'
        draw_url = f"{NEW_MARKET_BASE}/market/playoffic/draw"

        draw_info_resp = self.send_request(draw_info_url, headers=self.jwtHeaders, cookies=self.cookies)
        if draw_info_resp is None:
            print('❌抽奖信息查询失败')
            return
        draw_info_data = draw_info_resp.json()

        if draw_info_data.get('msg') == 'success':
            remain_num = draw_info_data.get('result', {}).get('surplusNumber', 0)
            print(f'剩余抽奖次数{remain_num}')
            if remain_num > 50 - self.draw:
                for _ in range(self.draw):
                    self.sleep()
                    draw_resp = self.send_request(url=draw_url, headers=self.jwtHeaders, cookies=self.cookies)
                    if draw_resp is None:
                        continue
                    draw_data = draw_resp.json()

                    if draw_data.get("code") == 0:
                        prize_name = draw_data.get("result", {}).get("prizeName", "")
                        print("✅抽奖成功，获得:" + prize_name)
                    else:
                        print("❌抽奖失败")
            else:
                pass
        else:
            print(draw_info_data.get('msg'))
            self.log_info(draw_info_data.get('msg'))

    # 果园专区 — 修复Cookie提取
    @catch_errors
    def fruitLogin(self):
        token = self.sso()
        if token is not None:
            print("-果园专区token刷新成功")
            self.sleep()
            login_info_url = f'{self.fruit_url}login/caiyunsso.do?token={token}&account={self.account}&targetSourceId=001208&sourceid=1003&enableShare=1'
            headers = {
                'Host': 'happy.mail.10086.cn',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': ua,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'Referer': 'https://m.mcloud.139.com/',
                'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            # 修复: 使用session发起请求，从response.cookies中提取Cookie
            loginInfoData = requests.request("GET", login_info_url, headers=headers)

            # 修复Cookie提取: 优先从response.cookies获取，fallback到request.headers['Cookie']
            tree_cookie = ''
            if loginInfoData.cookies:
                # 从response cookies构建cookie字符串
                cookie_parts = []
                for name, value in loginInfoData.cookies.items():
                    cookie_parts.append(f'{name}={value}')
                tree_cookie = '; '.join(cookie_parts)

            if not tree_cookie:
                # fallback: 尝试从请求头获取
                try:
                    tree_cookie = loginInfoData.request.headers.get('Cookie', '')
                except (KeyError, AttributeError):
                    tree_cookie = ''

            if not tree_cookie:
                print('❌果园登录Cookie获取失败')
                return

            self.treeHeaders['cookie'] = tree_cookie

            do_login_url = f'{self.fruit_url}login/userinfo.do'
            doLoginData = self.send_request(do_login_url, headers=self.treeHeaders)
            if doLoginData is None:
                print('❌果园登录请求失败')
                return
            doLoginData = doLoginData.json()
            if doLoginData.get('result', {}).get('islogin') != 1:
                return print('❌果园登录失败')
            # 去做果园任务
            self.fruitTask()
        else:
            print("果园专区token刷新失败")

    # 任务查询
    @catch_errors
    def fruitTask(self):
        # 签到任务
        check_sign_data = self.send_request(f'{self.fruit_url}task/checkinInfo.do',
                                            headers=self.treeHeaders)
        if check_sign_data is None:
            print('-果园签到查询失败')
            return
        check_sign_data = check_sign_data.json()
        if check_sign_data.get('success'):
            today_checkin = check_sign_data.get('result', {}).get('todayCheckin', 0)
            if today_checkin == 1:
                print('-果园今日已签到')
            else:
                checkin_data = self.send_request(f'{self.fruit_url}task/checkin.do',
                                                 headers=self.treeHeaders)
                if checkin_data and checkin_data.json().get('result', {}).get('code', '') == 1:
                    print('-果园签到成功')
                self.sleep()
                water_data = self.send_request(f'{self.fruit_url}user/clickCartoon.do?cartoonType=widget',
                                               headers=self.treeHeaders)
                color_data = self.send_request(f'{self.fruit_url}user/clickCartoon.do?cartoonType=color',
                                               headers=self.treeHeaders)
                if water_data:
                    given_water = water_data.json().get('result', {}).get('given', 0)
                    print(f'-领取每日水滴: {given_water}')
                if color_data:
                    print(f'-每日雨滴:{color_data.json().get("result", {}).get("msg", "")}')
        else:
            print('-果园签到查询失败:', check_sign_data.get('msg', ''))

        # 获取任务列表
        task_list_data = self.send_request(f'{self.fruit_url}task/taskList.do?clientType=PE',
                                           headers=self.treeHeaders)
        task_state_data = self.send_request(f'{self.fruit_url}task/taskState.do', headers=self.treeHeaders)
        if task_list_data is None or task_state_data is None:
            print('-果园任务列表获取失败')
            return
        task_state_result = task_state_data.json().get('result', [])

        task_list = task_list_data.json().get('result', [])

        for task in task_list:
            task_id = task.get('taskId', '')
            task_name = task.get('taskName', '')
            water_num = task.get('waterNum', 0)
            if task_id == 2002 or task_id == 2003:
                continue

            task_state = next(
                (state.get('taskState', 0) for state in task_state_result if state.get('taskId') == task_id), 0)

            if task_state == 2:
                print(f'-已完成: {task_name}')
            else:
                self.do_fruit_task(task_name, task_id, water_num)

        # 果树信息
        self.tree_info()

    # 做任务
    @catch_errors
    def do_fruit_task(self, task_name, task_id, water_num):
        print(f'-去完成: {task_name}')
        do_task_url = f'{self.fruit_url}task/doTask.do?taskId={task_id}'
        do_task_data = self.send_request(do_task_url, headers=self.treeHeaders)
        if do_task_data is None:
            return
        do_task_data = do_task_data.json()

        if do_task_data.get('success'):
            get_water_url = f'{self.fruit_url}task/givenWater.do?taskId={task_id}'
            get_water_data = self.send_request(get_water_url, headers=self.treeHeaders)
            if get_water_data and get_water_data.json().get('success'):
                print(f'-已完成任务获得水滴: {water_num}')
            else:
                print(f'❌领取失败: {get_water_data.json().get("msg", "") if get_water_data else "请求失败"}')
        else:
            print(f'❌参与任务失败: {do_task_data.get("msg", "")}')

    # 果树信息
    @catch_errors
    def tree_info(self):
        treeinfo_url = f'{self.fruit_url}user/treeInfo.do'
        treeinfo_data = self.send_request(treeinfo_url, headers=self.treeHeaders)
        if treeinfo_data is None:
            print('-果树信息获取失败')
            return
        treeinfo_data = treeinfo_data.json()

        if not treeinfo_data.get('success'):
            error_message = treeinfo_data.get('msg', '获取果园任务列表失败')
            print(error_message)
        else:
            collect_water = treeinfo_data.get('result', {}).get('collectWater', 0)
            tree_level = treeinfo_data.get('result', {}).get('treeLevel', 0)
            print(f'-当前小树等级: {tree_level} 剩余水滴: {collect_water}')
            if tree_level in (2, 4, 6, 8):
                # 开宝箱
                openbox_url = f'{self.fruit_url}prize/openBox.do'
                openbox_data = self.send_request(openbox_url, headers=self.treeHeaders)
                if openbox_data:
                    print(f'- {openbox_data.json().get("result", {}).get("msg", "")}')

            watering_amount = collect_water // 20  # 计算需要浇水的次数
            watering_url = f'{self.fruit_url}user/watering.do?isFast=0'
            if watering_amount > 0:
                for _ in range(watering_amount):
                    watering_data = self.send_request(watering_url, headers=self.treeHeaders)
                    if watering_data and watering_data.json().get('success'):
                        print('✔️ 浇水成功')
                        time.sleep(3)
            else:
                print('-水滴不足!')

    # 云朵大作战 — 新域名
    @catch_errors
    def cloud_game(self):
        game_info_url = f'{NEW_MARKET_BASE}/market/signin/hecheng1T/info?op=info'
        bigin_url = f'{NEW_MARKET_BASE}/market/signin/hecheng1T/beinvite'
        end_url = f'{NEW_MARKET_BASE}/market/signin/hecheng1T/finish?flag=true'

        game_info_resp = self.send_request(game_info_url, headers=self.jwtHeaders, cookies=self.cookies)
        if game_info_resp is None:
            print("-获取游戏信息失败")
            return
        game_info_data = game_info_resp.json()
        if game_info_data and game_info_data.get('code', -1) == 0:
            currnum = game_info_data.get('result', {}).get('info', {}).get('curr', 0)
            count = game_info_data.get('result', {}).get('history', {}).get('0', {}).get('count', '')
            rank = game_info_data.get('result', {}).get('history', {}).get('0', {}).get('rank', '')

            print(f'今日剩余游戏次数: {currnum}\n本月排名: {rank}    合成次数: {count}')

            for _ in range(currnum):
                self.send_request(bigin_url, headers=self.jwtHeaders, cookies=self.cookies)
                print('-开始游戏,等待10-15秒完成游戏')
                time.sleep(random.randint(10, 15))
                end_resp = self.send_request(end_url, headers=self.jwtHeaders, cookies=self.cookies)
                if end_resp and end_resp.json().get('code', -1) == 0:
                    print('游戏成功')
        else:
            print("-获取游戏信息失败")

    # 领取云朵 — 使用receiveV2
    @catch_errors
    def receive(self):
        receive_url = f"{NEW_MARKET_BASE}/market/signin/page/receiveV2?client=app"
        prize_url = f"{NEW_MARKET_BASE}/market/prizeApi/checkPrize/getUserPrizeLogPage?currPage=1&pageSize=15&_={self.timestamp}"
        receive_resp = self.send_request(receive_url, headers=self.jwtHeaders, cookies=self.cookies)
        self.sleep()
        prize_resp = self.send_request(prize_url, headers=self.jwtHeaders, cookies=self.cookies)

        if receive_resp is None or prize_resp is None:
            print('❌领取云朵请求失败')
            return

        prize_data = prize_resp.json()
        result = prize_data.get('result', {}).get('result', [])
        rewards = ''
        if result:
            for value in result:
                prizeName = value.get('prizeName')
                flag = value.get('flag')
                if flag == 1:
                    rewards += f'-待领取奖品: {prizeName}\n'

        receive_data = receive_resp.json()
        receive_amount = receive_data.get("result", {}).get("receive", "")
        total_amount = receive_data.get("result", {}).get("total", "")
        print(f'\n-当前待领取:{receive_amount}云朵')
        print(f'-当前云朵数量:{total_amount}云朵')
        msg = f'云朵数量:{total_amount} \n{rewards}'
        self.log_info(amount=msg)

    # 备份云朵 — 新域名
    @catch_errors
    def backup_cloud(self):
        backup_url = f'{NEW_MARKET_BASE}/market/backupgift/info'
        backup_resp = self.send_request(backup_url, headers=self.jwtHeaders, cookies=self.cookies)
        if backup_resp is None:
            print('❌备份云朵查询失败')
            return
        backup_data = backup_resp.json()
        state = backup_data.get('result', {}).get('state', '')
        if state == -1:
            print('本月未备份,暂无连续备份奖励')

        elif state == 0:
            print('-领取本月连续备份奖励')
            cur_url = f'{NEW_MARKET_BASE}/market/backupgift/receive'
            cur_resp = self.send_request(cur_url, headers=self.jwtHeaders, cookies=self.cookies)
            if cur_resp:
                cur_data = cur_resp.json()
                print(f'-获得云朵数量:{cur_data.get("result", {}).get("result", "")}')

        elif state == 1:
            print('-已领取本月连续备份奖励')
        self.sleep()
        expend_url = f'{NEW_MARKET_BASE}/market/signin/page/taskExpansion'  # 每月膨胀云朵
        expend_resp = self.send_request(expend_url, headers=self.jwtHeaders, cookies=self.cookies)
        if expend_resp is None:
            print('❌膨胀云朵查询失败')
            return
        expend_data = expend_resp.json()

        curMonthBackup = expend_data.get('result', {}).get('curMonthBackup', '')  # 本月备份
        preMonthBackup = expend_data.get('result', {}).get('preMonthBackup', '')  # 上月备份
        curMonthBackupTaskAccept = expend_data.get('result', {}).get('curMonthBackupTaskAccept', '')  # 本月是否领取
        nextMonthTaskRecordCount = expend_data.get('result', {}).get('nextMonthTaskRecordCount', '')  # 下月备份云朵
        acceptDate = expend_data.get('result', {}).get('acceptDate', '')  # 月份

        if curMonthBackup:
            print(f'- 本月已备份，下月可领取膨胀云朵: {nextMonthTaskRecordCount}')
        else:
            print('- 本月还未备份，下月暂无膨胀云朵')

        if preMonthBackup:
            if curMonthBackupTaskAccept:
                print('- 上月已备份，膨胀云朵已领取')
            else:
                # 领取
                receive_url = f'{NEW_MARKET_BASE}/market/signin/page/receiveTaskExpansion?acceptDate={acceptDate}'
                receive_resp = self.send_request(receive_url, headers=self.jwtHeaders,
                                                 cookies=self.cookies)
                if receive_resp is None:
                    print('-领取膨胀云朵请求失败')
                    return
                receive_data = receive_resp.json()
                if receive_data.get("code") != 0:
                    print(f'-领取失败:{receive_data.get("msg")}')
                else:
                    cloudCount = receive_data.get('result', {}).get('cloudCount', '')
                    print(f'- 膨胀云朵领取成功: {cloudCount}朵')
        else:
            print('-上月未备份，本月无膨胀云朵领取')

    # 通知云朵 — 新域名
    @catch_errors
    def open_send(self):
        send_url = f'{NEW_MARKET_BASE}/market/msgPushOn/task/status'
        send_resp = self.send_request(send_url, headers=self.jwtHeaders, cookies=self.cookies)
        if send_resp is None:
            print('❌通知任务查询失败')
            return
        send_data = send_resp.json()

        pushOn = send_data.get('result', {}).get('pushOn', '')  # 0未开启，1开启，2未领取，3已领取
        firstTaskStatus = send_data.get('result', {}).get('firstTaskStatus', '')
        secondTaskStatus = send_data.get('result', {}).get('secondTaskStatus', '')
        onDuaration = send_data.get('result', {}).get('onDuaration', '')  # 开启时间

        if pushOn == 1:
            reward_url = f'{NEW_MARKET_BASE}/market/msgPushOn/task/obtain'

            if firstTaskStatus == 3:
                print('- 任务1奖励已领取')
            else:
                # 领取任务1
                print('- 领取任务1奖励')
                reward1_data = self.send_request(reward_url, headers=self.jwtHeaders, data={"type": 1},
                                                 method="POST")
                if reward1_data:
                    print(reward1_data.json().get('result', {}).get('description', ''))

            if secondTaskStatus == 2:
                # 领取任务2
                print('- 领取任务2奖励')
                reward2_data = self.send_request(reward_url, headers=self.jwtHeaders, data={"type": 2},
                                                 method="POST")
                if reward2_data:
                    print(reward2_data.json().get('result', {}).get('description', ''))

            print(f'- 通知已开启天数: {onDuaration}, 满31天可领取奖励')
        else:
            print('- 通知权限未开启')


if __name__ == "__main__":
    env_name = 'ydypCK'
    token = os.getenv(env_name)
    if not token:
        print(f'⛔️未获取到ck变量：请检查变量 {env_name} 是否填写')
        exit(0)

    cookies = re.split(r'[@\n]', token)
    print(f"移动硬盘共获取到{len(cookies)}个账号")

    for i, account_info in enumerate(cookies, start=1):
        print(f"\n======== ▷ 第 {i} 个账号 ◁ ========")
        YP(account_info).run()
        print("\n随机等待5-10s进行下一个账号")
        time.sleep(random.randint(5, 10))

    # 输出异常账号信息
    if err_accounts != '':
        print(f"\n失效账号:\n{err_accounts}")
    else:
        print('当前所有账号ck有效')
    if err_message != '':
        print(f'-错误信息: \n{err_message}')
    print(user_amount)
    # 在load_send中获取导入的send函数
    send = load_send()

    # # 判断send是否可用再进行调用
    if send:
        msg = f"云朵数量: \n{user_amount}"
        send('中国移动云盘任务信息', msg)
    else:
        print('通知服务不可用')
