-- 创建数据库（请按需在 psql 控制台或客户端执行）
-- CREATE DATABASE pupu_housekeeper WITH ENCODING = 'UTF8';

-- ========================================================
-- 1. 客户/供应商（往来单位表）
-- 支持：应收款(人)、应付款(人) 统计
-- ========================================================
CREATE TABLE partner (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL,
  phone VARCHAR(20) DEFAULT NULL,
  type SMALLINT NOT NULL DEFAULT 1, -- 类型：1-客户 2-供应商 3-二者皆是
  receivable_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00, -- 当前应收款金额(元)
  payable_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00, -- 当前应付款金额(元)
  remark VARCHAR(255) DEFAULT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 添加索引与注释
CREATE INDEX idx_partner_phone ON partner(phone);
CREATE INDEX idx_partner_type ON partner(type);

COMMENT ON TABLE partner IS '往来单位表（客户/供应商）';
COMMENT ON COLUMN partner.id IS '主键ID';
COMMENT ON COLUMN partner.name IS '姓名/单位名称';
COMMENT ON COLUMN partner.type IS '类型：1-客户 2-供应商 3-二者皆是';
COMMENT ON COLUMN partner.receivable_amount IS '当前应收款金额(元)';
COMMENT ON COLUMN partner.payable_amount IS '当前应付款金额(元)';

-- ========================================================
-- 2. 存货/设备/配件 库存表
-- 支持：新机库存、二手机库存、配件库存、在库设备总值
-- ========================================================
-- Drop table

-- DROP TABLE public.inventory;

CREATE TABLE public.inventory (
	id bigserial NOT NULL,
	sn_code varchar(100) NULL DEFAULT NULL::character varying,
	title varchar(100) NOT NULL,
	category int2 NOT NULL,
	spec varchar(100) NULL DEFAULT NULL::character varying,
	purchase_price numeric(10, 2) NOT NULL DEFAULT 0.00,
	selling_price numeric(10, 2) NOT NULL DEFAULT 0.00,
	stock_quantity int4 NOT NULL DEFAULT 1,
	status int2 NOT NULL DEFAULT 1,
	supplier_id int8 NULL,
	in_stock_time timestamptz NULL DEFAULT CURRENT_TIMESTAMP,
	created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
	remark varchar(255) NULL DEFAULT NULL::character varying,
	shop_id int4 NOT NULL,
	CONSTRAINT inventory_pkey PRIMARY KEY (id),
	CONSTRAINT inventory_sn_code_key UNIQUE (sn_code),
	CONSTRAINT fk_inventory_shops FOREIGN KEY (shop_id) REFERENCES public.shops(id) ON DELETE CASCADE,
	CONSTRAINT inventory_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.partner(id) ON DELETE SET NULL
);
CREATE INDEX idx_inventory_cat_status ON public.inventory USING btree (category, status);
CREATE INDEX idx_inventory_shop_id ON public.inventory USING btree (shop_id);
CREATE INDEX idx_inventory_supplier_id ON public.inventory USING btree (supplier_id);


COMMENT ON TABLE inventory IS '库存物品表';

COMMENT ON COLUMN public.inventory.id IS '主键ID（自动递增）';
COMMENT ON COLUMN public.inventory.sn_code IS '序列号/SN码/IMEI码（唯一识别码）';
COMMENT ON COLUMN public.inventory.title IS '设备/商品名称或标题（如：iPhone 15 Pro）';
COMMENT ON COLUMN public.inventory.category IS '分类类型（如 1:新机, 2:二手机, 3:配件）';
COMMENT ON COLUMN public.inventory.spec IS '规格描述/配置（如：256G 黑色 / 极佳）';
COMMENT ON COLUMN public.inventory.purchase_price IS '回收/采购成本价（元）';
COMMENT ON COLUMN public.inventory.selling_price IS '预售/标价/出货指导价（元）';
COMMENT ON COLUMN public.inventory.stock_quantity IS '库存数量（设备通常为 1，配件可多件）';
COMMENT ON COLUMN public.inventory.status IS '库存状态（如 1:在库/待售, 2:已售出, 3:维修复测中, 4:已退货）';
COMMENT ON COLUMN public.inventory.supplier_id IS '关联供应商/回收来源ID（外键关联 partner 表）';
COMMENT ON COLUMN public.inventory.in_stock_time IS '设备实际入库/收货时间';
COMMENT ON COLUMN public.inventory.created_at IS '记录创建时间';
COMMENT ON COLUMN public.inventory.updated_at IS '记录最近更新时间';
COMMENT ON COLUMN public.inventory.remark IS '备注说明（如：微瑕、换过电池等细节）';
COMMENT ON COLUMN public.inventory.shop_id IS '所属店铺ID（外键关联 shops 表，多店铺数据隔离）';

-- ========================================================
-- 3. 日常收付款流水表
-- 支持：今日收入、今日支出、今日毛利计算
-- ========================================================
-- Drop table

-- DROP TABLE public.financial_record;

CREATE TABLE public.financial_record (
	id bigserial NOT NULL,
	record_sn varchar(64) NOT NULL,
	"type" int2 NOT NULL,
	category varchar(50) NOT NULL,
	amount numeric(10, 2) NOT NULL DEFAULT 0.00,
	profit numeric(10, 2) NOT NULL DEFAULT 0.00,
	partner_id int8 NULL,
	business_type int2 NULL DEFAULT 0,
	business_id int8 NULL,
	payment_method varchar(30) NULL DEFAULT '微信'::character varying,
	record_time timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
	remark varchar(255) NULL DEFAULT NULL::character varying,
	created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
	shop_id int4 NOT NULL,
	device_sn_code varchar(100) NULL DEFAULT NULL::character varying,
	CONSTRAINT financial_record_pkey PRIMARY KEY (id),
	CONSTRAINT financial_record_record_sn_key UNIQUE (record_sn),
	CONSTRAINT financial_record_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.partner(id) ON DELETE SET NULL,
	CONSTRAINT fk_financial_record_inventory FOREIGN KEY (device_sn_code) REFERENCES public.inventory(sn_code) ON DELETE SET NULL,
	CONSTRAINT fk_financial_records_shops FOREIGN KEY (shop_id) REFERENCES public.shops(id) ON DELETE CASCADE
);
CREATE INDEX idx_financial_device_sn ON public.financial_record USING btree (device_sn_code);
CREATE INDEX idx_financial_partner_id ON public.financial_record USING btree (partner_id);
CREATE INDEX idx_financial_record_time ON public.financial_record USING btree (record_time);
CREATE INDEX idx_financial_shop_time ON public.financial_record USING btree (shop_id, record_time);
CREATE INDEX idx_financial_type_time ON public.financial_record USING btree (type, record_time);


COMMENT ON TABLE financial_record IS '日常收付款流水表';

-- ========================================================
-- 4. 维修工单表
-- 支持：维修开单、维修记录
-- ========================================================
CREATE TABLE repair_order (
  id BIGSERIAL PRIMARY KEY,
  repair_sn VARCHAR(64) NOT NULL UNIQUE, -- 维修单号
  customer_id BIGINT NOT NULL REFERENCES partner(id),
  device_model VARCHAR(100) NOT NULL, -- 维修设备型号
  device_sn VARCHAR(100) DEFAULT NULL,
  fault_description TEXT,
  quoted_price NUMERIC(10,2) NOT NULL DEFAULT 0.00, -- 维修报价(元)
  cost_price NUMERIC(10,2) NOT NULL DEFAULT 0.00, -- 维修成本(元)
  status SMALLINT NOT NULL DEFAULT 1, -- 状态：1-待检测 2-维修中 3-已完工 4-已取机/结单 5-已取消
  repairman_name VARCHAR(50) DEFAULT NULL,
  completion_time TIMESTAMP WITH TIME ZONE DEFAULT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_repair_customer_id ON repair_order(customer_id);
CREATE INDEX idx_repair_status ON repair_order(status);

COMMENT ON TABLE repair_order IS '维修工单表';

-- ========================================================
-- 5. 出库/销售订单表
-- 支持：手机出库、配件出库
-- ========================================================
CREATE TABLE outbound_order (
  id BIGSERIAL PRIMARY KEY,
  order_sn VARCHAR(64) NOT NULL UNIQUE, -- 出库单号
  customer_id BIGINT DEFAULT NULL REFERENCES partner(id),
  outbound_type SMALLINT NOT NULL, -- 1-手机出库 2-配件出库
  total_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00, -- 订单总金额(元)
  total_profit NUMERIC(10,2) NOT NULL DEFAULT 0.00, -- 订单总毛利(元)
  payment_status SMALLINT NOT NULL DEFAULT 1, -- 1-已全额付款 2-挂账/未全额付 3-未付款
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_outbound_customer_id ON outbound_order(customer_id);
CREATE INDEX idx_outbound_created_at ON outbound_order(created_at);

COMMENT ON TABLE outbound_order IS '出库/销售订单表';

-- ========================================================
-- 6. 出库订单明细表
-- ========================================================
CREATE TABLE outbound_order_item (
  id BIGSERIAL PRIMARY KEY,
  outbound_order_id BIGINT NOT NULL REFERENCES outbound_order(id) ON DELETE CASCADE,
  inventory_id BIGINT NOT NULL REFERENCES inventory(id),
  quantity INT NOT NULL DEFAULT 1,
  purchase_price NUMERIC(10,2) NOT NULL DEFAULT 0.00, -- 出库时成本
  selling_price NUMERIC(10,2) NOT NULL DEFAULT 0.00, -- 实际成交单价
  profit NUMERIC(10,2) NOT NULL DEFAULT 0.00 -- 单项毛利
);

CREATE INDEX idx_outbound_item_order_id ON outbound_order_item(outbound_order_id);
CREATE INDEX idx_outbound_item_inventory_id ON outbound_order_item(inventory_id);

COMMENT ON TABLE outbound_order_item IS '出库订单明细表';

-- ========================================================
-- 7. user login
-- ========================================================
-- public.sys_user definition

-- Drop table

-- DROP TABLE public.sys_user;

CREATE TABLE public.sys_user (
	id bigserial NOT NULL,
	openid varchar(64) NOT NULL,
	unionid varchar(64) NULL DEFAULT NULL::character varying,
	nickname varchar(64) NULL DEFAULT '微信用户'::character varying,
	avatar_url varchar(255) NULL DEFAULT ''::character varying,
	phone varchar(20) NULL DEFAULT NULL::character varying,
	"role" varchar(20) NULL DEFAULT 'staff'::character varying,
	created_at timestamptz NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at timestamptz NULL DEFAULT CURRENT_TIMESTAMP,
	is_active bool NULL DEFAULT true, -- 账号状态：true-启用/激活，false-禁用
	CONSTRAINT sys_user_openid_key UNIQUE (openid),
	CONSTRAINT sys_user_pkey PRIMARY KEY (id)
);
CREATE INDEX idx_user_openid ON public.sys_user USING btree (openid);

-- Column comments

COMMENT ON COLUMN public.sys_user.is_active IS '账号状态：true-启用/激活，false-禁用';

-- Permissions

ALTER TABLE public.sys_user OWNER TO postgres;
GRANT ALL ON TABLE public.sys_user TO postgres;
GRANT ALL ON TABLE public.sys_user TO anon;
GRANT ALL ON TABLE public.sys_user TO authenticated;
GRANT ALL ON TABLE public.sys_user TO service_role;

-- ========================================================
-- 8. shop
-- ========================================================
-- 1. 创建 shops 表 (PostgreSQL 语法)
-- Drop table
-- DROP TABLE public.shops;

CREATE TABLE public.shops (
	id serial4 NOT NULL,
	owner_id int4 NOT NULL, -- 新增：店主/创建者ID
	"name" varchar(100) NOT NULL,
	logo varchar(255) NULL DEFAULT ''::character varying,
	contact_name varchar(50) NULL DEFAULT ''::character varying,
	contact_phone varchar(20) NULL DEFAULT ''::character varying,
	province varchar(50) NULL DEFAULT ''::character varying,
	city varchar(50) NULL DEFAULT ''::character varying,
	district varchar(50) NULL DEFAULT ''::character varying,
	address_detail varchar(255) NULL DEFAULT ''::character varying,
	is_active bool NULL DEFAULT true,
	created_at timestamp NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at timestamp NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT shops_pkey PRIMARY KEY (id),
	CONSTRAINT fk_shops_owner FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE RESTRICT
);

-- 为常用查询字段建立索引
CREATE INDEX idx_shops_owner_id ON public.shops USING btree (owner_id);

-- 添加表与字段注释 (PostgreSQL 规范写法)
COMMENT ON TABLE shops IS '店铺基础信息表';
COMMENT ON COLUMN shops.id IS '店铺ID';
COMMENT ON COLUMN shops.name IS '店铺名称';
COMMENT ON COLUMN shops.logo IS '店铺LOGO图片地址';
COMMENT ON COLUMN shops.contact_name IS '联系人姓名';
COMMENT ON COLUMN shops.contact_phone IS '联系电话';
COMMENT ON COLUMN shops.province IS '省/地区';
COMMENT ON COLUMN shops.city IS '城市';
COMMENT ON COLUMN shops.district IS '区县';
COMMENT ON COLUMN shops.address_detail IS '详细地址';
COMMENT ON COLUMN shops.is_active IS '店铺状态：true-正常，false-禁用';

-- ========================================================
-- 9. staff
-- ========================================================
-- 创建 shop_staff 表
CREATE TABLE IF NOT EXISTS shop_staff (
    id BIGSERIAL PRIMARY KEY,
    shop_id INT NOT NULL,
    user_id BIGINT DEFAULT NULL,
    name VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'staff',
    status SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 添加索引以提升查询性能
CREATE INDEX idx_shop_staff_shop_id ON shop_staff (shop_id);
CREATE INDEX idx_shop_staff_user_id ON shop_staff (user_id);

-- 添加外键约束 (可选，建议按项目规范配置)
ALTER TABLE shop_staff 
    ADD CONSTRAINT fk_shop_staff_user 
    FOREIGN KEY (user_id) REFERENCES sys_user(id) 
    ON DELETE SET NULL;

-- 字段注释
COMMENT ON TABLE shop_staff IS '店铺员工/成员档案表';
COMMENT ON COLUMN shop_staff.id IS '主键ID';
COMMENT ON COLUMN shop_staff.shop_id IS '关联店铺ID';
COMMENT ON COLUMN shop_staff.user_id IS '绑定的真实微信用户ID(未接受邀请前为NULL)';
COMMENT ON COLUMN shop_staff.name IS '员工姓名/备注名';
COMMENT ON COLUMN shop_staff.role IS '角色权限: owner(店长)/manager(经理)/staff(店员)';
COMMENT ON COLUMN shop_staff.status IS '状态: 0-待接受邀请, 1-正常在职, 2-已离职/禁用';