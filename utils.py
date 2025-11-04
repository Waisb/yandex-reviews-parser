import time

import undetected_chromedriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from yandex_reviews_parser.parsers import Parser


class YandexParser:
    def __init__(
        self,
        driver_executable_path: str | None = None,
        browser_executable_path: str | None = None,
    ):
        """
        Инициализация парсера БЕЗ указания ya_id.
        ID передаём уже в метод parse().
        """
        self.driver_executable_path = driver_executable_path
        self.browser_executable_path = browser_executable_path

    def __create_driver(self):
        """
        Создаём Chrome с включёнными performance-логами,
        как нужно для чтения fetchReviews (аналогично code_3).
        """
        opts = undetected_chromedriver.ChromeOptions()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("headless")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")

        caps = DesiredCapabilities.CHROME.copy()
        caps["goog:loggingPrefs"] = {"performance": "ALL"}
        opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        driver = undetected_chromedriver.Chrome(
            options=opts,
            driver_executable_path=self.driver_executable_path,
            browser_executable_path=self.browser_executable_path,
            desired_capabilities=caps,
        )
        return driver

    def __open_page(self, id_yandex: int) -> Parser:
        """
        Открываем страницу отзывов по конкретному ID.
        """
        driver = self.__create_driver()
        url: str = f"https://yandex.ru/maps/org/{id_yandex}/reviews/"
        parser = Parser(driver)
        driver.get(url)
        return parser

    def get_company_id_from_url(self, url: str, timeout: int = 10) -> int | None:
        """
        Открывает переданный URL Яндекс.Карт и вытаскивает businessId (ya_id)
        через сетевые логи (fetchReviews), используя Parser.get_business_id_from_network().
        """
        driver = self.__create_driver()
        parser = Parser(driver)
        try:
            driver.get(url)
            # даём странице время отправить запрос fetchReviews
            time.sleep(4)
            biz_id = parser.get_business_id_from_network(timeout=timeout)
            return int(biz_id) if biz_id is not None else None
        finally:
            driver.close()
            driver.quit()
    def parse(
        self,
        id_yandex: int,
        type_parse: str = "default",
        sort: str | None = "newest",
        limit: int = -1,
    ) -> dict:
        """
        type_parse:
          - 'default'  — компания + отзывы
          - 'company'  — только информация о компании
          - 'reviews'  — только отзывы

        sort  — тип сортировки для отзывов
        limit — макс. количество отзывов (-1 = все)
        """
        result: dict = {}
        page = self.__open_page(id_yandex)
        time.sleep(4)
        try:
            if type_parse == "default":
                result = page.parse_all_data(sort=sort, limit=limit)
            elif type_parse == "company":
                result = page.parse_company_info()
            elif type_parse == "reviews":
                result = page.parse_reviews(sort=sort, limit=limit)
        except Exception as e:
            print(e)
            return result
        finally:
            page.driver.close()
            page.driver.quit()
            return result