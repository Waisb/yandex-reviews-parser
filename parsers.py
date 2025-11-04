import json
import re
import time
from dataclasses import asdict
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, JavascriptException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from yandex_reviews_parser.helpers import ParserHelper
from yandex_reviews_parser.storage import Review, Info


class Parser:
    ORG_NAME_XPATH = ".//h1[@class='orgpage-header-view__header']"
    REVIEWS_CLASS = "business-reviews-card-view__review"

    def __init__(self, driver, wait_timeout: int = 10):
        self.driver = driver
        self.wait = WebDriverWait(driver, wait_timeout)

        # Кеш последнего fetchReviews
        # {
        #   "business_id": "4987...",
        #   "url": ".../fetchReviews?...",
        #   "request_id": "...",
        # }
        self._last_fetch: Optional[dict] = None

        # Включаем Network в CDP 
        try:
            self.driver.execute_cdp_cmd("Network.enable", {})
        except Exception:
            pass

    def _perf_messages(self) -> list:
        """Снимаем и парсим performance-логи из Chrome DevTools."""
        logs = []
        try:
            raw = self.driver.get_log("performance")
        except Exception:
            return []
        for e in raw:
            try:
                msg = json.loads(e["message"])["message"]
                logs.append(msg)
            except Exception:
                continue
        return logs

    def _collect_fetch_from_logs(
        self,
        timeout: int = 10,
        business_id: Optional[str] = None,
    ) -> bool:
        """
        Читает performance-логи и сохраняет инфу о последнем успешном
        fetchReviews запросе в self._last_fetch.

        Если business_id передан, фильтруем по нему.
        Если не передан, берём первый попавшийся fetchReviews (и сам вытащим id).
        """
        end_time = time.time() + timeout

        while time.time() < end_time:
            msgs = self._perf_messages()

            for m in msgs:
                if m.get("method") != "Network.responseReceived":
                    continue

                params = m.get("params", {})
                response_meta = params.get("response", {})
                url = response_meta.get("url", "")
                status = response_meta.get("status")
                req_id = params.get("requestId")

                if "fetchReviews" not in url:
                    continue
                if status != 200:
                    continue

                bid_match = re.search(r"businessId=(\d+)", url)
                found_bid = bid_match.group(1) if bid_match else None

                if business_id and found_bid and found_bid != business_id:
                    continue
                if business_id and not found_bid:
                    continue

                self._last_fetch = {
                    "business_id": found_bid,
                    "url": url,
                    "request_id": req_id,
                }

            if self._last_fetch:
                return True

            time.sleep(0.3)

        return False

    def get_business_id_from_network(self, timeout: int = 10) -> Optional[str]:
        """
        Возвращает businessId (ya_id) из сетевых логов.
        Аналог logic'е get_business_id_from_network из code_3.
        """
        if not self._last_fetch:
            self._collect_fetch_from_logs(timeout=timeout, business_id=None)

        if self._last_fetch and self._last_fetch.get("business_id"):
            return self._last_fetch["business_id"]

        return None

    def __scroll_to_bottom(self, limit: int = -1) -> None:
        """
        Скроллим список отзывов до конца или пока не соберём limit штук.
        limit = -1  -> скроллим до конца (старое поведение).
        """
        prev_count = 0

        while True:
            elements = self.driver.find_elements(By.CLASS_NAME, self.REVIEWS_CLASS)
            count = len(elements)

            if limit > 0 and count >= limit:
                break

            if count == prev_count:
                break

            prev_count = count

            if not elements:
                break

            last_elem = elements[-1]
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'end'});", last_elem
            )
            time.sleep(1)

    def __get_data_item(self, elem):
        """
        Спарсить данные по одному отзыву.
        """
        try:
            name = elem.find_element(By.XPATH, ".//span[@itemprop='name']").text
        except NoSuchElementException:
            name = None

        try:
            icon_style = elem.find_element(
                By.XPATH, ".//div[@class='user-icon-view__icon']"
            ).get_attribute("style")
            icon_href = icon_style.split('"')[1] if '"' in icon_style else None
        except NoSuchElementException:
            icon_href = None

        try:
            date_content = elem.find_element(
                By.XPATH, ".//meta[@itemprop='datePublished']"
            ).get_attribute("content")
            date = ParserHelper.form_date(date_content)
        except NoSuchElementException:
            date = None

        try:
            text = elem.find_element(
                By.CLASS_NAME, "business-review-view__body"
            ).text
        except NoSuchElementException:
            text = None

        stars_elems = elem.find_elements(
            By.CSS_SELECTOR, ".business-review-view__rating span"
        )
        stars = ParserHelper.get_count_star(stars_elems) if stars_elems else 0

        try:
            answer_btn = elem.find_element(
                By.CLASS_NAME, "business-review-view__comment-expand"
            )
            self.driver.execute_script("arguments[0].click()", answer_btn)
            answer = elem.find_element(
                By.CLASS_NAME, "business-review-comment-content__bubble"
            ).text
        except NoSuchElementException:
            answer = None

        item = Review(
            name=name,
            icon_href=icon_href,
            date=date,
            text=text,
            stars=stars,
            answer=answer,
        )
        return asdict(item)

    def __get_data_campaign(self) -> dict:
        """
        Получаем данные по компании.
        """
        try:
            name = self.driver.find_element(By.XPATH, self.ORG_NAME_XPATH).text
        except NoSuchElementException:
            name = None

        try:
            xpath_rating_block = (
                ".//div[@class='business-summary-rating-badge-view__rating-and-stars']"
            )
            rating_block = self.driver.find_element(By.XPATH, xpath_rating_block)

            xpath_rating = (
                ".//div[@class='business-summary-rating-badge-view__rating']"
                "/span[contains(@class, 'business-summary-rating-badge-view__rating-text')]"
            )
            rating_elems = rating_block.find_elements(By.XPATH, xpath_rating)
            rating = ParserHelper.format_rating(rating_elems)

            xpath_count_rating = (
                ".//div[@class='business-summary-rating-badge-view__rating-count']"
                "/span[@class='business-rating-amount-view _summary']"
            )
            count_rating_text = rating_block.find_element(
                By.XPATH, xpath_count_rating
            ).text
            count_rating = ParserHelper.list_to_num(count_rating_text)

            xpath_stars = ".//div[@class='business-rating-badge-view__stars']/span"
            stars_elems = rating_block.find_elements(By.XPATH, xpath_stars)
            stars = ParserHelper.get_count_star(stars_elems) if stars_elems else 0
        except NoSuchElementException:
            rating = 0
            count_rating = 0
            stars = 0

        item = Info(
            name=name,
            rating=rating,
            count_rating=count_rating,
            stars=stars,
        )
        return asdict(item)
    
    def __set_reviews_sort(self, sort: str | None = None) -> None:
        """
        Устанавливает сортировку отзывов.

        sort:
          - 'default'   — По умолчанию
          - 'newest'    — По новизне
          - 'negative'  — Сначала отрицательные
          - 'positive'  — Сначала положительные
        """
        if not sort:
            return

        label_map = {
            "default": "По умолчанию",
            "newest": "По новизне",
            "negative": "Сначала отрицательные",
            "positive": "Сначала положительные",
        }
        label = label_map.get(sort)
        if not label:
            print(f"[sort={sort}] неизвестный тип сортировки")
            return

        try:
            # <div class="rating-ranking-view" role="button" ...>
            toggle = None
            for _ in range(20):  # до ~10 секунд
                candidates = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div.rating-ranking-view[role='button']",
                )
                visible = [c for c in candidates if c.is_displayed()]
                if visible:
                    toggle = visible[0]
                    break
                time.sleep(0.5)

            if not toggle:
                print(f"[sort={sort}] не нашёл кнопку сортировки")
                return
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", toggle
            )
            self.driver.execute_script("arguments[0].click();", toggle)
            time.sleep(0.7)  # даём попапу появиться

            target = None
            last_visible_count = 0

            for _ in range(20):  # до ~10 секунд
                lines = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div.rating-ranking-view__popup-line",
                )
                visible = [ln for ln in lines if ln.is_displayed()]
                last_visible_count = len(visible)

                for ln in visible:
                    aria = (ln.get_attribute("aria-label") or "").strip()
                    text = (ln.text or "").strip()
                    if aria == label or text == label:
                        target = ln
                        break

                if target:
                    break
                time.sleep(0.5)

            if not target:
                print(
                    f"[sort={sort}] не нашёл пункт '{label}', "
                    f"видимых строк: {last_visible_count}"
                )
                return

            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", target
            )
            self.driver.execute_script("arguments[0].click();", target)
            time.sleep(1.0)  # даём странице перерисовать отзывы

        except Exception as e:
            print(f"[sort={sort}] ошибка при применении сортировки: {e}")

    def __get_data_reviews(
        self,
        sort: str | None = None,
        limit: int = -1,
    ) -> list:
        """
        Собирает отзывы.

        sort  — тип сортировки (None / 'default' / 'newest' / 'negative' / 'positive')
        limit — максимальное количество отзывов:
                -1  -> все
                >0  -> не больше указанного количества
        """
        #сортировка до сбора
        self.__set_reviews_sort(sort)

        reviews: list = []

        # скроллим пока не наберём limit или не дойдём до конца
        self.__scroll_to_bottom(limit=limit)

        elements = self.driver.find_elements(By.CLASS_NAME, self.REVIEWS_CLASS)

        if limit > 0:
            elements = elements[:limit]

        for elem in elements:
            reviews.append(self.__get_data_item(elem))

        return reviews



    def __is_valid_page(self) -> bool:
        try:
            self.driver.find_element(By.XPATH, self.ORG_NAME_XPATH)
            return True
        except NoSuchElementException:
            return False

    def parse_all_data(
        self,
        sort: str | None = None,
        limit: int = -1,
    ) -> dict:
        if not self.__is_valid_page():
            return {"error": "Страница не найдена"}
        return {
            "company_info": self.__get_data_campaign(),
            "company_reviews": self.__get_data_reviews(sort=sort, limit=limit),
        }

    def parse_reviews(
        self,
        sort: str | None = None,
        limit: int = -1,
    ) -> dict:
        if not self.__is_valid_page():
            return {"error": "Страница не найдена"}
        return {"company_reviews": self.__get_data_reviews(sort=sort, limit=limit)}
    
    def parse_company_info(self) -> dict:
        if not self.__is_valid_page():
            return {"error": "Страница не найдена"}
        return {"company_info": self.__get_data_campaign()}
