from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.command_processor import CommandProcessor
from database.db import get_db
from repositories.module_repository import ModuleRepository

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("/")
def list_modules(db: Session = Depends(get_db)):
    return ModuleRepository(db).list_modules()


@router.post("/")
def create_module(
    module_public_key: str,
    name: str,
    call_name: str | None = None,
    custom_call_name: str | None = None,
    description: str = "",
    parent_module_id: int | None = None,
    db: Session = Depends(get_db),
):
    processor = CommandProcessor(ModuleRepository(db))
    return processor.create_module(
        module_public_key=module_public_key.strip(),
        name=name.strip(),
        call_name=call_name.strip() if call_name else None,
        custom_call_name=custom_call_name.strip() if custom_call_name else None,
        description=description.strip(),
        parent_module_id=parent_module_id,
    )
