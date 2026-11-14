from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from src.config.database import db_session
from src.controllers.auth import current_user,writer
from src.models import ShipmentAnalysis
from src.schemas.shipment import ShipmentInput
from src.services import shipments as service
from src.utils.serialization import rows,serialize
router=APIRouter(prefix="/shipments")
@router.get("")
def listing(db=Depends(db_session),user=Depends(current_user)):
 return rows(db.scalars(select(ShipmentAnalysis).order_by(ShipmentAnalysis.created_at.desc())))
@router.post("")
def create(payload:ShipmentInput,db=Depends(db_session),user=Depends(writer)):
 return service.create(db,payload,user)
@router.get("/{id}")
def detail(id:str,db=Depends(db_session),user=Depends(current_user)):
 item=db.get(ShipmentAnalysis,id)
 if not item:raise HTTPException(404,"限时发运分析不存在")
 data=serialize(item)
 # 半成品不向前端暴露：未完成时不返回检查点与结果
 if item.status!="completed":
  data["result"]={}
 data["checkpoint"]={}
 return data
