import re
import hashlib
import logging
from typing import Generator, Dict, Any, List, Optional
from connectors.base import BaseConnector
from core.models import Document
import httpx

logger = logging.getLogger(__name__)

def extract_notion_id(raw_input: str) -> str:
    """Extract clean 32-char hex ID from either raw ID or full Notion URL."""
    clean = raw_input.strip().split("?")[0]
    match = re.search(r'([a-f0-9]{32})', clean.replace('-', ''))
    if match:
        return match.group(1)
    return clean.split("/")[-1]

def map_course(title: str, parent_course: str = "MAGISTRALE") -> str:
    t = title.upper()
    if "DISTRIBUITI" in t or "SDCC" in t:
        return "SDCC"
    if "SECURITY" in t or "CNS" in t or "SICUREZZA" in t:
        return "CNS"
    if "MACHINE" in t or "LEARNING" in t or "ML" in t:
        return "ML"
    if "EMBEDDED" in t or "SE" in t:
        return "SE"
    return parent_course

class NotionConnector(BaseConnector):
    def __init__(self, api_key: str, database_id: str):
        self.api_key = api_key.strip() if api_key else ""
        self.root_id = extract_notion_id(database_id) if database_id else ""
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        self.base_url = "https://api.notion.com/v1"

    def extract(self) -> Generator[Document, None, None]:
        if not self.api_key or not self.root_id:
            raise ValueError("Notion API Key e Database/Page ID sono obbligatori nel file .env.")

        with httpx.Client(headers=self.headers, timeout=20.0) as client:
            visited_pages = set()
            visited_dbs = set()
            
            # Queue holds tuples: (entity_type, entity_id, course_context, depth)
            # Try to see if root is page or database
            queue = [("page", self.root_id, "MAGISTRALE", 0)]

            while queue:
                entity_type, entity_id, course_context, depth = queue.pop(0)

                if depth > 4:
                    continue

                if entity_type == "page":
                    if entity_id in visited_pages:
                        continue
                    visited_pages.add(entity_id)

                    doc, child_items = self._process_page(client, entity_id, course_context, depth)
                    if doc:
                        yield doc

                    for c_type, c_id, c_course in child_items:
                        queue.append((c_type, c_id, c_course, depth + 1))

                elif entity_type == "database":
                    if entity_id in visited_dbs:
                        continue
                    visited_dbs.add(entity_id)

                    child_pages = self._process_database(client, entity_id, course_context)
                    for c_id, c_course in child_pages:
                        queue.append(("page", c_id, c_course, depth + 1))

    def _process_page(self, client: httpx.Client, page_id: str, course_context: str, depth: int):
        try:
            resp = client.get(f"{self.base_url}/pages/{page_id}")
            if resp.status_code != 200:
                return None, []
            page_data = resp.json()
        except Exception as e:
            logger.warning(f"Errore recupero pagina {page_id}: {e}")
            return None, []

        title, props_md = self._extract_properties(page_data)
        course = map_course(title, course_context)
        url = page_data.get("url", "")
        last_edited = page_data.get("last_edited_time")

        # Fetch blocks and discover child pages/databases
        blocks_text, child_items = self._fetch_blocks_recursive(client, page_id, course)

        full_md_parts = []
        if title:
            full_md_parts.append(f"# {title}\n")
        if props_md:
            full_md_parts.append(props_md + "\n")
        if blocks_text:
            full_md_parts.append(blocks_text)

        full_text = "\n".join(full_md_parts).strip()
        if not full_text:
            return None, child_items

        checksum = hashlib.sha256(full_text.encode('utf-8')).hexdigest()

        doc = Document(
            id=f"notion-{page_id}",
            source_type="notion",
            source_id=page_id,
            title=title or "Untitled Notion Page",
            uri=url,
            course=course,
            mime_type="text/markdown",
            checksum=checksum,
            metadata={
                "raw_text": full_text,
                "last_edited": last_edited,
                "notion_depth": depth
            }
        )
        return doc, child_items

    def _process_database(self, client: httpx.Client, db_id: str, course_context: str) -> List[tuple]:
        child_pages = []
        cursor = None
        while True:
            try:
                payload = {}
                if cursor:
                    payload["start_cursor"] = cursor
                resp = client.post(f"{self.base_url}/databases/{db_id}/query", json=payload)
                if resp.status_code != 200:
                    break
                data = resp.json()
            except Exception as e:
                logger.warning(f"Errore query database {db_id}: {e}")
                break

            for p in data.get("results", []):
                p_id = p.get("id")
                p_title, _ = self._extract_properties(p)
                p_course = map_course(p_title, course_context)
                child_pages.append((p_id, p_course))

            if not data.get("has_more") or not data.get("next_cursor"):
                break
            cursor = data.get("next_cursor")

        return child_pages

    def _extract_properties(self, page_data: Dict[str, Any]) -> tuple:
        title = "Untitled"
        props = page_data.get("properties", {})
        details = []

        for k, v in props.items():
            prop_type = v.get("type")
            if prop_type == "title":
                t_arr = v.get("title", [])
                if t_arr:
                    title = "".join(t.get("plain_text", "") for t in t_arr)
            elif prop_type == "multi_select":
                vals = [x.get("name", "") for x in v.get("multi_select", [])]
                if vals:
                    details.append(f"**{k}:** {', '.join(vals)}")
            elif prop_type == "select":
                sel = v.get("select")
                if sel and sel.get("name"):
                    details.append(f"**{k}:** {sel.get('name')}")
            elif prop_type == "url" and v.get("url"):
                details.append(f"**{k}:** {v.get('url')}")
            elif prop_type == "rich_text":
                rt_arr = v.get("rich_text", [])
                if rt_arr:
                    text_val = "".join(t.get("plain_text", "") for t in rt_arr)
                    details.append(f"**{k}:** {text_val}")

        props_md = " | ".join(details) if details else ""
        return title, props_md

    def _fetch_blocks_recursive(self, client: httpx.Client, block_id: str, course: str) -> tuple:
        lines = []
        child_items = []
        cursor = None

        while True:
            try:
                params = {}
                if cursor:
                    params["start_cursor"] = cursor
                resp = client.get(f"{self.base_url}/blocks/{block_id}/children", params=params)
                if resp.status_code != 200:
                    break
                data = resp.json()
            except Exception as e:
                logger.warning(f"Errore lettura blocchi {block_id}: {e}")
                break

            results = data.get("results", [])
            for b in results:
                btype = b.get("type")
                if btype == "child_page":
                    ctitle = b.get("child_page", {}).get("title", "Untitled")
                    c_course = map_course(ctitle, course)
                    child_items.append(("page", b["id"], c_course))
                    continue
                elif btype == "child_database":
                    dtitle = b.get("child_database", {}).get("title", "Untitled")
                    d_course = map_course(dtitle, course)
                    child_items.append(("database", b["id"], d_course))
                    continue

                md = self._block_to_markdown(b)
                if md:
                    lines.append(md)

                # Nested children (like nested bullet lists, callouts, toggles)
                if b.get("has_children") and btype not in ("child_page", "child_database"):
                    nested_md, _ = self._fetch_blocks_recursive(client, b["id"], course)
                    if nested_md:
                        lines.append(nested_md)

            if not data.get("has_more") or not data.get("next_cursor"):
                break
            cursor = data.get("next_cursor")

        return "\n".join(lines), child_items

    def _block_to_markdown(self, b: Dict[str, Any]) -> str:
        btype = b.get("type")
        content = b.get(btype, {})
        if not isinstance(content, dict):
            return ""

        rt = content.get("rich_text", [])
        text = "".join(t.get("plain_text", "") for t in rt).strip()

        if btype == "paragraph":
            return text
        elif btype == "heading_1":
            return f"# {text}"
        elif btype == "heading_2":
            return f"## {text}"
        elif btype == "heading_3":
            return f"### {text}"
        elif btype == "bulleted_list_item":
            return f"- {text}"
        elif btype == "numbered_list_item":
            return f"1. {text}"
        elif btype == "to_do":
            checked = "x" if content.get("checked") else " "
            return f"- [{checked}] {text}"
        elif btype in ("callout", "quote"):
            return f"> {text}"
        elif btype == "code":
            lang = content.get("language", "")
            return f"```{lang}\n{text}\n```"
        elif btype == "divider":
            return "---"
        return text
