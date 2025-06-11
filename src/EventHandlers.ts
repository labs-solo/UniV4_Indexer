import { 
  PoolManager, 
  PositionManager,
  ERC20,
  Token, 
  Pool, 
  User, 
  Swap, 
  Position, 
  GlobalStats,
  PoolDayData 
} from "generated";

// Import BigDecimal correctly
import BigNumber from 'bignumber.js';
import type { t as BigDecimal_t } from 'envio/src/bindings/BigDecimal.gen';

// Helper function to create BigDecimal
function createBigDecimal(value: string | number | bigint): BigDecimal_t {
  return new BigNumber(value.toString());
}

// Helper function to create or get a token entity
async function getOrCreateToken(
  context: any,
  address: string,
  symbol: string = "UNKNOWN",
  name: string = "Unknown Token",
  decimals: number = 18
): Promise<Token> {
  let token = await context.Token.get(address);
  
  if (token === undefined) {
    let tokenObject: Token = {
      id: address,
      symbol,
      name,
      decimals,
      totalSupply: 0n,
    };
    context.Token.set(tokenObject);
    return tokenObject;
  }
  
  return token;
}

// Helper function to create or get a user entity
async function getOrCreateUser(context: any, address: string): Promise<User> {
  let user = await context.User.get(address);
  
  if (user === undefined) {
    let userObject: User = {
      id: address,
      positionCount: 0,
      swapCount: 0,
    };
    context.User.set(userObject);
    return userObject;
  }
  
  return user;
}

// Helper function to get or create global stats
async function getOrCreateGlobalStats(context: any): Promise<GlobalStats> {
  let stats = await context.GlobalStats.get("1");
  
  if (stats === undefined) {
    let statsObject: GlobalStats = {
      id: "1",
      poolCount: 0,
      transactionCount: 0,
      totalVolumeUSD: createBigDecimal("0"),
      totalTVL: createBigDecimal("0"),
      updatedAt: BigInt(Math.floor(Date.now() / 1000)),
    };
    context.GlobalStats.set(statsObject);
    return statsObject;
  }
  
  return stats;
}

// PoolManager Initialize event handler
PoolManager.Initialize.handler(async ({ event, context }) => {
  const poolId = event.params.id;
  const currency0 = event.params.currency0;
  const currency1 = event.params.currency1;
  const fee = event.params.fee;

  // Create or get tokens
  const token0 = await getOrCreateToken(context, currency0);
  const token1 = await getOrCreateToken(context, currency1);

  // Create pool entity
  const poolObject: Pool = {
    id: poolId,
    token0_id: currency0,
    token1_id: currency1,
    fee: Number(fee),
    poolManager: event.srcAddress,
    tick: 0,
    sqrtPriceX96: 0n,
    liquidity: 0n,
    createdAt: BigInt(event.block.timestamp),
    createdAtBlock: BigInt(event.block.number),
    volumeUSD: createBigDecimal("0"),
    tvlUSD: createBigDecimal("0"),
    feeGrowthGlobal0X128: 0n,
    feeGrowthGlobal1X128: 0n,
  };

  context.Pool.set(poolObject);

  // Update global stats
  const globalStats = await getOrCreateGlobalStats(context);
  const updatedGlobalStats: GlobalStats = {
    ...globalStats,
    poolCount: globalStats.poolCount + 1,
    updatedAt: BigInt(event.block.timestamp),
  };
  context.GlobalStats.set(updatedGlobalStats);
});

// PoolManager Swap event handler
PoolManager.Swap.handler(async ({ event, context }) => {
  const poolId = event.params.id;
  const sender = event.params.sender;
  const amount0 = event.params.amount0;
  const amount1 = event.params.amount1;
  const sqrtPriceX96 = event.params.sqrtPriceX96;
  const liquidity = event.params.liquidity;
  const tick = event.params.tick;

  // Get or create user
  const user = await getOrCreateUser(context, sender);
  
  // Get pool
  const pool = await context.Pool.get(poolId);
  if (pool === undefined) {
    console.error(`Pool ${poolId} not found for swap event`);
    return;
  }

  // Create swap entity - using block hash + log index for unique ID
  const swapId = `${event.block.hash}-${event.logIndex}`;
  const swapObject: Swap = {
    id: swapId,
    transaction: event.block.hash, // Using block hash since transaction hash not available
    pool_id: poolId,
    origin_id: sender,
    recipient: sender, // For now, assuming sender is recipient
    amount0: amount0,
    amount1: amount1,
    amountUSD: createBigDecimal("0"), // Would need price oracle to calculate
    tick: Number(tick), // Convert bigint to number
    sqrtPriceX96: sqrtPriceX96,
    liquidity: liquidity,
    gasUsed: 0n, // Transaction gas info not available in event
    gasPrice: 0n, // Transaction gas info not available in event
    timestamp: BigInt(event.block.timestamp),
    blockNumber: BigInt(event.block.number),
    logIndex: event.logIndex,
  };

  context.Swap.set(swapObject);

  // Update pool state - create new object since properties are readonly
  const updatedPool: Pool = {
    ...pool,
    tick: Number(tick),
    sqrtPriceX96: sqrtPriceX96,
    liquidity: liquidity,
  };
  context.Pool.set(updatedPool);

  // Update user stats - create new object since properties are readonly
  const updatedUser: User = {
    ...user,
    swapCount: user.swapCount + 1,
  };
  context.User.set(updatedUser);

  // Update global stats - create new object since properties are readonly
  const globalStats = await getOrCreateGlobalStats(context);
  const updatedGlobalStats: GlobalStats = {
    ...globalStats,
    transactionCount: globalStats.transactionCount + 1,
    updatedAt: BigInt(event.block.timestamp),
  };
  context.GlobalStats.set(updatedGlobalStats);
});

// PoolManager ModifyLiquidity event handler
PoolManager.ModifyLiquidity.handler(async ({ event, context }) => {
  const poolId = event.params.id;
  const sender = event.params.sender;
  const tickLower = event.params.tickLower;
  const tickUpper = event.params.tickUpper;
  const liquidityDelta = event.params.liquidityDelta;

  // Get or create user
  const user = await getOrCreateUser(context, sender);

  // Get pool
  const pool = await context.Pool.get(poolId);
  if (pool === undefined) {
    console.error(`Pool ${poolId} not found for modify liquidity event`);
    return;
  }

  // Create position ID
  const positionId = `${sender}-${poolId}-${tickLower}-${tickUpper}`;

  // Get or create position
  let position = await context.Position.get(positionId);
  
  if (position === undefined) {
    // Create new position
    const positionObject: Position = {
      id: positionId,
      owner_id: sender,
      pool_id: poolId,
      tickLower: Number(tickLower), // Convert bigint to number
      tickUpper: Number(tickUpper), // Convert bigint to number
      liquidity: liquidityDelta > 0 ? liquidityDelta : 0n,
      depositedToken0: 0n,
      deposited1: 0n,
      withdrawnToken0: 0n,
      withdrawnToken1: 0n,
      collectedFeesToken0: 0n,
      collectedFeesToken1: 0n,
      createdAt: BigInt(event.block.timestamp),
      createdAtBlock: BigInt(event.block.number),
      updatedAt: BigInt(event.block.timestamp),
      updatedAtBlock: BigInt(event.block.number),
    };

    context.Position.set(positionObject);

    // Update user position count - create new object since properties are readonly
    const updatedUser: User = {
      ...user,
      positionCount: user.positionCount + 1,
    };
    context.User.set(updatedUser);
  } else {
    // Update existing position - create new object since properties are readonly
    const updatedPosition: Position = {
      ...position,
      liquidity: position.liquidity + liquidityDelta,
      updatedAt: BigInt(event.block.timestamp),
      updatedAtBlock: BigInt(event.block.number),
    };
    context.Position.set(updatedPosition);
  }
});

// PoolManager ProtocolFeeUpdated event handler
PoolManager.ProtocolFeeUpdated.handler(async ({ event, context }) => {
  const poolId = event.params.id;
  const protocolFee = event.params.protocolFee;

  // Get pool and update fee information if needed
  const pool = await context.Pool.get(poolId);
  if (pool !== undefined) {
    // Could add protocol fee field to pool schema if needed
    context.Pool.set(pool);
  }
});

// ERC20 Transfer event handler (for token tracking)
ERC20.Transfer.handler(async ({ event, context }) => {
  const from = event.params.from;
  const to = event.params.to;
  const value = event.params.value;
  const tokenAddress = event.srcAddress;

  // Update token total supply on mint/burn
  const token = await context.Token.get(tokenAddress);
  if (token !== undefined) {
    let newTotalSupply = token.totalSupply;
    
    // If from is zero address, it's a mint
    if (from === "0x0000000000000000000000000000000000000000") {
      newTotalSupply = token.totalSupply + value;
    }
    // If to is zero address, it's a burn
    else if (to === "0x0000000000000000000000000000000000000000") {
      newTotalSupply = token.totalSupply - value;
    }
    
    // Create new object since properties are readonly
    const updatedToken: Token = {
      ...token,
      totalSupply: newTotalSupply,
    };
    context.Token.set(updatedToken);
  }
});

// ERC20 Approval event handler (for completeness)
ERC20.Approval.handler(async ({ event, context }) => {
  // For now, we don't need to track approvals for Uniswap V4 indexing
  // But this handler is required since we're listening to the event
  // Could be used for analytics if needed
});

// PositionManager IncreaseLiquidity event handler
PositionManager.IncreaseLiquidity.handler(async ({ event, context }) => {
  const tokenId = event.params.tokenId;
  const liquidity = event.params.liquidity;
  const amount0 = event.params.amount0;
  const amount1 = event.params.amount1;

  // Note: We would need to track the relationship between tokenId and our position entities
  // For now, we'll log this information for analytics
  console.log(`IncreaseLiquidity: tokenId=${tokenId}, liquidity=${liquidity}, amount0=${amount0}, amount1=${amount1}`);
});

// PositionManager DecreaseLiquidity event handler
PositionManager.DecreaseLiquidity.handler(async ({ event, context }) => {
  const tokenId = event.params.tokenId;
  const liquidity = event.params.liquidity;
  const amount0 = event.params.amount0;
  const amount1 = event.params.amount1;

  // Note: We would need to track the relationship between tokenId and our position entities
  // For now, we'll log this information for analytics
  console.log(`DecreaseLiquidity: tokenId=${tokenId}, liquidity=${liquidity}, amount0=${amount0}, amount1=${amount1}`);
});

// PositionManager Collect event handler
PositionManager.Collect.handler(async ({ event, context }) => {
  const tokenId = event.params.tokenId;
  const recipient = event.params.recipient;
  const amount0 = event.params.amount0;
  const amount1 = event.params.amount1;

  // Note: This represents fee collection from a position
  // We would want to update the position's collected fees
  console.log(`Collect: tokenId=${tokenId}, recipient=${recipient}, amount0=${amount0}, amount1=${amount1}`);
});
