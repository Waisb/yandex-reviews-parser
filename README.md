
# Яндекс карты, парсер отзывов.

**Код является доработкой чужого исходника!**  
Оригинальный код -> [![github](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/useless-apple/yandex_reviews-parser)
---
Использование - получение business_id из ссылки:
```python
from yandex_reviews_parser.utils import YandexParser

#Ссылка из яндекс карт с открытым разделом отзывов
url = ("https://yandex.ru/maps/org/tsentralnaya_klinicheskaya_psikhiatricheskaya_bolnitsa_moskovskoy_oblasti_detskoye_dispansernoye_otdeleniye/1040226791/reviews/?ll=37.555796%2C55.799275&tab=reviews&z=17.1")

parser = YandexParser()

#Получаем ID компании по ссылке
id_yandex = parser.get_company_id_from_url(url, timeout=10)
print(f"Найден business_id: {id_yandex}")

#-> 1040226791
```

Использование - получение информации по business_id:
```python
from yandex_reviews_parser.utils import YandexParser
id_ya = 1234 #business_id
parser = YandexParser(id_ya)
all_data = parser.parse() #Получаем все данные
```
Вывод:
```json
{'company_info': 
{
'name': 'Центральная клиническая психиатрическая больница Московской области, детское диспансерное отделение', 'rating': 3.7, 
'count_rating': 114, 
'stars': 0},
'company_reviews': [
{
'name': 'Evgen Evgen', 
'icon_href': 'https://avatars.mds.yandex.net/get-yapic/37154/0y-1/islands-68', 
'date': 1760071873.496, 
'text': 'Всем доброго дня, точнее доброго здоровья! ⚕️ Меня зовут Евгений Николаевич, хочу поделиться мнением и оставить отзыв о ДИСПАНСЕРНОМ ОТДЕЛЕНИИ ПСИХИАТРИЧЕСКОЙ БОЛЬНИЦЫ ИМЕНИ Ф. А. Усольцева…\nещё',
'stars': 5, 
'answer': 'Спасибо за приятный отзыв!'
},
...
]
```
--- 
Метод parse может принимать параметр type_parse:

| Parameter | Type     | Description                |
| :-------- | :------- | :------------------------- |
| `'default'` | `string` | *Optional/by default* - Получение всех данных. |
| `'company'` | `string` | *Optional* - Получение только информации о компании. |
| `'reviews'` | `string` | *Optional* - Получение только отзывов. |
 
--- 
## Зависимости (установка):
```bash
pip install -r requirements.txt
```
---
Пример полноценного запроса:  
```python
from yandex_reviews_parser.utils import YandexParser
#Инициализация парсера
parser = YandexParser()
#Ссылка прямо с карт для отлова iD компании
url = ("https://yandex.ru/maps/org/tsentralnaya_klinicheskaya_psikhiatricheskaya_bolnitsa_moskovskoy_oblasti_detskoye_dispansernoye_otdeleniye/1040226791/reviews/?ll=37.555796%2C55.799275&tab=reviews&z=17.1")
#Получение ID компании из ссылки
id_yandex = parser.get_company_id_from_url(url, timeout=10)

if id_yandex is None:
    raise RuntimeError("Не удалось получить ID компании")
#Получение всех данных компании по ID
all_data = parser.parse(id_yandex=id_yandex, type_parse="default")
print (all_data)
```

## Известные проблемы:
Проблема в undetected_chromedriver.
```bash
..\Lib\site-packages\undetected_chromedriver\__init__.py", line 843, in __del__
    time.sleep(0.1)
OSError: [WinError 6] Неверный дескриптор
```
Исправление (undetected_chromedriver\__init__.py строки с 798 по 801) замена для time.sleep(0.1):
```python
try:
    time.sleep(0.1)
except OSError:
    pass
```
