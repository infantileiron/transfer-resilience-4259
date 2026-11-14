from pydantic import BaseModel,Field,model_validator
MAX_HOURS=72
class ShipmentInput(BaseModel):
 run_id:str
 name:str=Field(min_length=2,max_length=120)
 total_cargo:int=Field(ge=1,le=10**9)
 deadline_hours:int=Field(ge=1,le=MAX_HOURS)
 # 每个中转站的库存上限（箱）；源站与汇站不限，无需提供
 stock_limits:dict[str,int]=Field(default_factory=dict)
 @model_validator(mode="after")
 def valid(self):
  for node,cap in self.stock_limits.items():
   if not isinstance(node,str) or not node:raise ValueError("中转站代码须为非空字符串")
   if isinstance(cap,bool) or not isinstance(cap,int) or cap<0:
    raise ValueError(f"中转站 {node} 库存上限须为非负整数")
  return self
