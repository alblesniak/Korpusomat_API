import os
import json
import requests
import time
from bs4 import BeautifulSoup
from requests_toolbelt import MultipartEncoder


class KorpusomatApiRequest():

    def __init__(self, user_email=os.environ["KORPUSOMAT_EMAIL"], user_password=os.environ["KORPUSOMAT_PASSWORD"], base_url="http://korpusomat.pl"):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Mobile Safari/537.36"
        }
        self.base_url = base_url
        try:
            login_resp = self.session.get(
                self.base_url + "/login", headers=self.headers)
        except:
            raise Exception("Connection failed.")
        login_soup = BeautifulSoup(login_resp.content, "html5lib")
        self.user_email = user_email
        self.user_password = user_password
        self.csrf_token = login_soup.find(
            'input', {'id': 'csrf_token'})['value']

    def login(self):
        login_data = {
            "email": self.user_email,
            "password": self.user_password,
            "csrf_token": self.csrf_token
        }
        auth_resp = self.session.post(
            self.base_url + "/login", data=login_data, headers=self.headers)

        # Login check
        auth_soup = BeautifulSoup(auth_resp.content, "html5lib")
        last_nav_item = auth_soup.find("ul", {"class": "nav"}).find_all(
            "li")[-1].get_text(strip=True)
        if last_nav_item != "Wyloguj":
            raise Exception("Username or password is incorrect.")
        else:
            print("Login successful.")

    def logout(self):
        logout_resp = self.session.get(self.base_url + "/logout")
        self.session.close()
        print("Logout Status:", logout_resp.status_code)
        return logout_resp

    def all_corpora(self):
        all_corpora_list = []
        corpora_resp = self.session.get(
            self.base_url + "/corpora", headers=self.headers)
        corpora_soup = BeautifulSoup(corpora_resp.content, "html5lib")
        table_soup = corpora_soup.find("table", {"id": "corpora-table"})
        for table_row in table_soup.find("tbody").find_all("tr"):
            corpus_data = table_row.find_all("td")
            corpus_dict = {
                "corpus_name": corpus_data[0].find("a").get_text(strip=True),
                "corpus_id": int(corpus_data[0].find("a")["href"].replace("/corpus/", "")),
                "number_of_texts": int(corpus_data[1].get_text(strip=True)),
                "number_of_tokens": int(corpus_data[2].get_text(strip=True) or 0),
                "status": corpus_data[3].get_text(strip=True)
            }
            all_corpora_list.append(corpus_dict)
        return all_corpora_list

    def all_texts(self, corpus_id):
        all_texts_list = []
        texts_resp = self.session.get(
            self.base_url + "/corpus-fragment/" + str(corpus_id), headers=self.headers)
        texts_soup = BeautifulSoup(texts_resp.content, "html5lib")
        table_soup = texts_soup.find("table", {"class": "table"})
        for table_row in table_soup.find("tbody").find_all("tr"):
            text_data = table_row.find_all("td")
            text_dict = {
                "file_name": text_data[0].find("a").get_text(strip=True),
                "file_url": self.base_url + text_data[0].find("a", href=True)["href"],
                "author": text_data[1].get_text(strip=True),
                "number_of_tokens": text_data[2].get_text(strip=True),
                "percentage": text_data[3].get_text(strip=True),
                "text_id": int(text_data[5].find("a")["data-text-id"])
            }
            all_texts_list.append(text_dict)
            procceding = False
        return all_texts_list

    def add_corpus(self, corpus_name):
        add_corpus_resp = self.session.post("http://korpusomat.pl/create-corpus", headers=self.headers,
                                            data={
                                                "csrf_token": self.csrf_token,
                                                "name": corpus_name
                                            })
        print(f"Corpus {corpus_name} has been created.")
        # Check for all corpora with name corpus_name and if there is more than 1 choose one with greatest id number.
        same_named_corpora = []
        for corpus in self.all_corpora():
            if corpus["corpus_name"] == corpus_name:
                same_named_corpora.append(corpus)
        if len(same_named_corpora) > 1:
            corpora_ids = []
            for corpus in same_named_corpora:
                corpora_ids.append(corpus["corpus_id"])
            return same_named_corpora[corpora_ids.index(max(corpora_ids))]
        else:
            return same_named_corpora[0]

    def remove_corpus(self, corpus_id):
        remove_resp = self.session.get(
            self.base_url + "/remove-corpus/" + str(corpus_id), headers=self.headers)
        print(f"Corpus {str(corpus_id)} has been removed.")

    def add_text(self, corpus_id, file_path, text_author=None, text_title=None, text_publish_date=None, text_genre=None):
        scripts_dir = os.path.dirname(__file__)
        absolute_file_path = os.path.join(scripts_dir, file_path)
        upload_resp = self.session.post(self.base_url + "/+upload", files={
            "files": (os.path.basename(file_path), open(absolute_file_path, "rb"))
        })
        resp_data = json.loads(upload_resp.text)[0]
        print(resp_data)
        file_name = resp_data["filename"]
        file_src_name = resp_data["src_name"]
        if text_title == None:
            text_title = resp_data["title"]
        m = MultipartEncoder(fields={
            "meta1[]": text_author,
            "meta2[]": text_title,
            "meta3[]": text_publish_date,
            "meta4[]": text_genre,
            "file_src_name[]": file_src_name,
            "file_name[]": file_name
        })
        add_text_resp = self.session.post(
            self.base_url + "/add-text/" + str(corpus_id), data=m, headers={
                "User-Agent": self.headers["User-Agent"],
                "Content-Type": m.content_type
            })
        print(
            f"Text-file {file_src_name} has been added to corpus {corpus_id}")
        # Wait to load all files in corpus and check for all files with name file_name and if there is more than 1 choose one with greatest id number.
        same_named_texts = []
        procceding = True
        while procceding == True:
            try:
                for text in self.all_texts(corpus_id):
                    if text["file_name"] == file_src_name:
                        same_named_texts.append(text)
                if len(same_named_texts) > 1:
                    print(">1")
                    texts_ids = []
                    for sn_text in same_named_texts:
                        texts_ids.append(sn_text["text_id"])
                    return same_named_texts[texts_ids.index(max(texts_ids))]
                else:
                    print("!>1")
                    return same_named_texts[0]
            except AttributeError:
                print("File procceding in progress... Sleeping for 1 second")
                time.sleep(1)
                continue
            except TypeError:
                print("File procceding in progress... Sleeping for 1 second")
                time.sleep(1)
                continue


korp = KorpusomatApiRequest()
korp.login()
result = korp.add_text(corpus_id=717, file_path="Zupełnie-inny.txt")
print(result)
korp.logout()
