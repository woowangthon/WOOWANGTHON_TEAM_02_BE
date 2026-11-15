from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Attachment:
    name: str
    url: str


@dataclass(frozen=True)
class Notice:
    department: str
    post_number: str
    title: str
    author: str
    date: str
    url: str
    content: str
    attachments: list[Attachment]
    collected_at: str = ""

    def as_dict(self) -> dict:
        result = asdict(self)
        result["attachments"] = [asdict(item) for item in self.attachments]
        return result
