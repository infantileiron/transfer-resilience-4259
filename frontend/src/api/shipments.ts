import {request,post} from './client';import type {Shipment} from '../types/domain';
export const list=()=>request<Shipment[]>('/shipments');
export const create=(data:unknown)=>post<Shipment>('/shipments',data);
