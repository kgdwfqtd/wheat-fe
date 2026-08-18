# -*- coding: utf-8 -*-
"""数据库初始化脚本"""
import asyncio
import sys
import os

# Windows 下确保 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mobile_api.database import engine, Base, AsyncSessionLocal
from mobile_api.models import Plot, User, ExperimentBase
from mobile_api.auth import hash_password
from mobile_api.utils import BLOCKS, TREATMENT_CODES, make_plot_code
import sqlalchemy


async def init_database():
    """初始化数据库"""
    print("[INIT] 开始初始化数据库...")

    # 创建表
    print("[INIT] 创建表结构...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[INIT] 表结构创建完成")

    # 初始化数据
    async with AsyncSessionLocal() as session:
        base_result = await session.execute(
            sqlalchemy.select(ExperimentBase).where(ExperimentBase.base_code == "000000000000")
        )
        default_base = base_result.scalar_one_or_none()
        if default_base is None:
            default_base = ExperimentBase(
                base_code="000000000000",
                base_name="默认试验基地",
                admin_code="000000",
                remarks="兼容旧数据",
            )
            session.add(default_base)
            await session.flush()

        # 检查小区
        result = await session.execute(sqlalchemy.select(sqlalchemy.func.count()).select_from(Plot))
        plot_count = result.scalar_one()

        if plot_count == 0:
            print("[INIT] 初始化 18 个小区...")
            for block in BLOCKS:
                for trt in TREATMENT_CODES:
                    code = make_plot_code(block, trt)
                    session.add(Plot(base_code=default_base.base_code, block=block, treatment=trt, plot_code=code, area_m2=20.0))
            await session.commit()
            print("[INIT] 小区数据初始化完成")
        else:
            print(f"[INIT] 已有 {plot_count} 个小区，跳过初始化")

        # 检查用户
        result2 = await session.execute(sqlalchemy.select(sqlalchemy.func.count()).select_from(User))
        user_count = result2.scalar_one()

        if user_count == 0:
            print("[INIT] 创建默认用户账户...")
            # 安全警告：首次部署后请立即修改默认密码！
            session.add(User(username='admin', password_hash=hash_password('admin123'), real_name='系统管理员', role='admin', is_active=True))
            session.add(User(username='field', password_hash=hash_password('field123'), real_name='田间采集员', role='user', is_active=True))
            await session.commit()
            print("[INIT] 用户账户创建完成")
            print("   ⚠️ 安全警告：默认密码为弱密码，首次登录后请立即修改！")
            print("   管理员: admin / admin123")
            print("   采集员: field / field123")
        else:
            print(f"[INIT] 已有 {user_count} 个用户，跳过初始化")

    print("\n[INIT] 数据库初始化完成!")


if __name__ == "__main__":
    asyncio.run(init_database())
