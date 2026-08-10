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
	CONSTRAINT inventory_pkey PRIMARY KEY (id),
	CONSTRAINT inventory_sn_code_key UNIQUE (sn_code),
	CONSTRAINT inventory_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.partner(id) ON DELETE SET NULL
);
CREATE INDEX idx_inventory_cat_status ON public.inventory USING btree (category, status);
CREATE INDEX idx_inventory_supplier_id ON public.inventory USING btree (supplier_id);

COMMENT ON TABLE inventory IS '库存物品表';

-- ========================================================
-- 3. 日常收付款流水表
-- 支持：今日收入、今日支出、今日毛利计算
-- ========================================================
CREATE TABLE financial_record (
  id BIGSERIAL PRIMARY KEY,
  record_sn VARCHAR(64) NOT NULL UNIQUE, -- 流水单号
  type SMALLINT NOT NULL, -- 类型：1-收入 2-支出
  category VARCHAR(50) NOT NULL, -- 收支科目
  amount NUMERIC(10,2) NOT NULL DEFAULT 0.00, -- 交易金额(元)
  profit NUMERIC(10,2) NOT NULL DEFAULT 0.00, -- 产生毛利(元)
  partner_id BIGINT DEFAULT NULL REFERENCES partner(id) ON DELETE SET NULL,
  business_type SMALLINT DEFAULT 0, -- 关联业务类型：0-无 1-手机出库 2-配件出库 3-维修结算 4-挂账还款
  business_id BIGINT DEFAULT NULL, -- 关联具体业务单据ID
  payment_method VARCHAR(30) DEFAULT '微信',
  record_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  remark VARCHAR(255) DEFAULT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_financial_record_time ON financial_record(record_time);
CREATE INDEX idx_financial_type_time ON financial_record(type, record_time);
CREATE INDEX idx_financial_partner_id ON financial_record(partner_id);

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
-- DROP TABLE public.sys_user;

CREATE TABLE public.sys_user (
	id bigserial NOT NULL,
	openid varchar(64) NOT NULL,
	unionid varchar(64) NULL DEFAULT NULL::character varying,
	nickname varchar(64) NULL DEFAULT '微信用户'::character varying,
	avatar_url varchar(255) NULL DEFAULT ''::character varying,
	phone varchar(20) NULL DEFAULT NULL::character varying,
	"role" varchar(20) NULL DEFAULT 'staff'::character varying,
	is_active bool NULL DEFAULT true, -- ⬅️ 新增：账号状态 (true-正常, false-禁用)
	created_at timestamptz NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at timestamptz NULL DEFAULT CURRENT_TIMESTAMP,
	shop_id int4 NULL DEFAULT 1,
	CONSTRAINT sys_user_openid_key UNIQUE (openid),
	CONSTRAINT sys_user_pkey PRIMARY KEY (id)
);

-- 创建索引与注释
CREATE INDEX idx_user_openid ON public.sys_user USING btree (openid);

COMMENT ON TABLE public.sys_user IS '系统用户/员工表';
COMMENT ON COLUMN public.sys_user.is_active IS '账号状态：true-启用，false-禁用';
COMMENT ON COLUMN public.sys_user.shop_id IS '关联店铺ID';

-- ========================================================
-- 8. shop
-- ========================================================
-- 1. 创建 shops 表 (PostgreSQL 语法)
CREATE TABLE IF NOT EXISTS shops (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  logo VARCHAR(255) DEFAULT '',
  contact_name VARCHAR(50) DEFAULT '',
  contact_phone VARCHAR(20) DEFAULT '',
  province VARCHAR(50) DEFAULT '',
  city VARCHAR(50) DEFAULT '',
  district VARCHAR(50) DEFAULT '',
  address_detail VARCHAR(255) DEFAULT '',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

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