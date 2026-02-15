"""
检查数据库中的 refresh token 记录
"""
import asyncio
from sqlalchemy import select
from app.dependencies import get_session_maker
from app.models.user import RefreshToken


async def check_tokens():
    session_maker = get_session_maker()
    async with session_maker() as session:
        # 查询所有 refresh tokens
        result = await session.execute(
            select(RefreshToken).order_by(RefreshToken.created_at.desc()).limit(10)
        )
        tokens = result.scalars().all()
        
        print(f'\n数据库中共有 {len(tokens)} 条最近的 refresh token 记录:\n')
        print("="*80)
        
        for i, token in enumerate(tokens, 1):
            print(f'\n记录 {i}:')
            print(f'  ID: {token.id}')
            print(f'  User ID: {token.user_id}')
            print(f'  JTI: {token.jti}')
            print(f'  Token (前60字符): {token.token[:60]}...')
            print(f'  Token (后60字符): ...{token.token[-60:]}')
            print(f'  创建时间: {token.created_at}')
            print(f'  最后使用: {token.last_used_at}')
            print(f'  过期时间: {token.expires_at}')
            print(f'  是否撤销: {token.is_revoked}')
            print(f'  设备信息: {token.device_info[:80] if token.device_info else None}...')
            print(f'  IP地址: {token.ip_address}')
            print("-"*80)
        
        # 检查是否有重复的 token
        print("\n检查 Token 唯一性:")
        token_values = [t.token for t in tokens]
        unique_tokens = set(token_values)
        print(f"  总记录数: {len(tokens)}")
        print(f"  唯一 Token 数: {len(unique_tokens)}")
        
        if len(tokens) != len(unique_tokens):
            print("  ⚠️  警告: 发现重复的 Token!")
            # 找出重复的 token
            from collections import Counter
            counter = Counter(token_values)
            duplicates = [token for token, count in counter.items() if count > 1]
            print(f"  重复的 Token 数量: {len(duplicates)}")
            for dup_token in duplicates:
                print(f"    - {dup_token[:60]}... (出现 {counter[dup_token]} 次)")
        else:
            print("  ✓ 所有 Token 都是唯一的")
        
        # 检查 JTI 唯一性
        print("\n检查 JTI 唯一性:")
        jti_values = [t.jti for t in tokens]
        unique_jtis = set(jti_values)
        print(f"  总记录数: {len(tokens)}")
        print(f"  唯一 JTI 数: {len(unique_jtis)}")
        
        if len(tokens) != len(unique_jtis):
            print("  ⚠️  警告: 发现重复的 JTI!")
        else:
            print("  ✓ 所有 JTI 都是唯一的")


if __name__ == "__main__":
    asyncio.run(check_tokens())

