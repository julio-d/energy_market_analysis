import pandas as pd

def calculate_arbitrage_benefits(omie_data, analysis_type, battery_capacity_mwh, efficiency, 
                                battery_cost_per_mwh, degradation_per_cycle):
    """Calculate arbitrage benefits for battery storage"""
    
    # Calculate daily max-min differences for each day
    df = omie_data.copy()
    df['date'] = pd.to_datetime(df.index).date
    
    if analysis_type == "1 Cycle":
        daily_arbitrage = calculate_1_cycle_arbitrage(df, efficiency)
    else:  # 2 Cycles
        daily_arbitrage = calculate_2_cycle_arbitrage(df, efficiency)
    
    daily_stats = pd.DataFrame(daily_arbitrage)
    
    # Apply degradation model
    daily_stats = apply_degradation_model(daily_stats, battery_capacity_mwh, 
                                         degradation_per_cycle, analysis_type)
    
    # Calculate ROI metrics
    roi_metrics = calculate_roi_metrics(daily_stats, battery_capacity_mwh, 
                                       battery_cost_per_mwh, degradation_per_cycle, analysis_type)
    
    # Add cycle statistics
    cycle_stats = calculate_cycle_statistics(daily_stats, analysis_type)
    
    return daily_stats, roi_metrics, cycle_stats

def calculate_1_cycle_arbitrage(df, efficiency):
    """Calculate 1-cycle arbitrage benefits"""
    daily_arbitrage = []
    
    for date in df['date'].unique():
        day_data = df[df['date'] == date].copy()
        day_data = day_data.sort_index()
        
        # Find the minimum price that occurs before 20:00
        prices_before_20h = day_data[day_data.index.hour < 20]
        
        if len(prices_before_20h) > 0:
            min_price = prices_before_20h['price'].min()
            min_time = prices_before_20h[prices_before_20h['price'] == min_price].index[0]
            
            # Find the maximum price that occurs AFTER the minimum
            prices_after_min = day_data[day_data.index > min_time]
        else:
            min_price = day_data['price'].min()
            min_time = day_data.index[0]
            prices_after_min = []
        
        if len(prices_after_min) > 0 and len(prices_before_20h) > 0:
            max_price_after_min = prices_after_min['price'].max()
            max_time = prices_after_min[prices_after_min['price'] == max_price_after_min].index[0]
            arbitrage_benefit = (max_price_after_min - min_price) * efficiency
            arbitrage_possible = True
        else:
            max_price_after_min = min_price
            max_time = min_time
            arbitrage_benefit = 0
            arbitrage_possible = False
        
        daily_arbitrage.append({
            'date': date,
            'min': min_price,
            'max': max_price_after_min,
            'min_time': min_time,
            'max_time': max_time,
            'arbitrage_possible': arbitrage_possible,
            'daily_benefit': arbitrage_benefit,
            'cycles_used': 1 if arbitrage_possible else 0
        })
    
    return daily_arbitrage

def calculate_2_cycle_arbitrage(df, efficiency):
    """Calculate 2-cycle arbitrage benefits"""
    daily_arbitrage = []
    
    for date in df['date'].unique():
        day_data = df[df['date'] == date].copy()
        day_data = day_data.sort_index()
        
        # Time windows for 2-cycle analysis
        min1_window = day_data[(day_data.index.hour >= 0) & (day_data.index.hour < 6)]   # 0h-6h
        max1_window = day_data[(day_data.index.hour >= 6) & (day_data.index.hour < 10)]  # 6h-10h
        min2_window = day_data[(day_data.index.hour >= 10) & (day_data.index.hour < 18)] # 10h-18h
        max2_window = day_data[(day_data.index.hour >= 18) & (day_data.index.hour < 24)] # 18h-24h
        
        # Check if all time windows have data
        if (len(min1_window) > 0 and len(max1_window) > 0 and 
            len(min2_window) > 0 and len(max2_window) > 0):
            
            # Find prices for each window
            min1_price = min1_window['price'].min()
            max1_price = max1_window['price'].max()
            min2_price = min2_window['price'].min()
            max2_price = max2_window['price'].max()
            
            # Calculate benefits for each cycle
            cycle1_benefit = (max1_price - min1_price) * efficiency
            cycle2_benefit = (max2_price - min2_price) * efficiency
            
            # Check if both cycles are profitable
            if cycle1_benefit > 0 and cycle2_benefit > 0:
                # Use 2-cycle strategy
                total_benefit = cycle1_benefit + cycle2_benefit
                cycles_used = 2
                arbitrage_possible = True
            else:
                # Fallback to 1-cycle strategy
                total_benefit, cycles_used, arbitrage_possible = fallback_to_1_cycle(day_data, efficiency)
        else:
            # Not enough data in time windows, fallback to 1-cycle
            total_benefit, cycles_used, arbitrage_possible = fallback_to_1_cycle(day_data, efficiency)
        
        daily_arbitrage.append({
            'date': date,
            'daily_benefit': total_benefit,
            'arbitrage_possible': arbitrage_possible,
            'cycles_used': cycles_used
        })
    
    return daily_arbitrage

def fallback_to_1_cycle(day_data, efficiency):
    """Fallback to 1-cycle strategy when 2-cycle is not optimal"""
    prices_before_20h = day_data[day_data.index.hour < 20]
    if len(prices_before_20h) > 0:
        min_price = prices_before_20h['price'].min()
        min_time = prices_before_20h[prices_before_20h['price'] == min_price].index[0]
        prices_after_min = day_data[day_data.index > min_time]
        
        if len(prices_after_min) > 0:
            max_price = prices_after_min['price'].max()
            total_benefit = (max_price - min_price) * efficiency
            cycles_used = 1
            arbitrage_possible = True
        else:
            total_benefit = 0
            cycles_used = 0
            arbitrage_possible = False
    else:
        total_benefit = 0
        cycles_used = 0
        arbitrage_possible = False
    
    return total_benefit, cycles_used, arbitrage_possible

def apply_degradation_model(daily_stats, battery_capacity_mwh, degradation_per_cycle, analysis_type):
    """Apply battery degradation model to daily statistics"""
    daily_stats = daily_stats.reset_index(drop=True)
    
    # Calculate cumulative cycles (accounting for days with 1 or 2 cycles)
    if analysis_type == "2 Cycles":
        daily_stats['cumulative_cycles'] = daily_stats['cycles_used'].cumsum()
    else:
        daily_stats['cumulative_cycles'] = daily_stats.index + 1
    
    daily_stats['remaining_capacity'] = battery_capacity_mwh * (1 - degradation_per_cycle) ** (daily_stats['cumulative_cycles'] - 1)
    daily_stats['degraded_benefit'] = daily_stats['daily_benefit'] * daily_stats['remaining_capacity']
    
    return daily_stats

def calculate_roi_metrics(daily_stats, battery_capacity_mwh, battery_cost_per_mwh, degradation_per_cycle, analysis_type):
    """Calculate ROI and investment metrics"""
    total_benefit = daily_stats['degraded_benefit'].sum()
    avg_daily_benefit = daily_stats['degraded_benefit'].mean()
    
    # Calculate yearly projection (proportional) - accounting for degradation
    if analysis_type == "2 Cycles":
        # For 2-cycle analysis, estimate based on average cycles per day
        avg_cycles_per_day = daily_stats['cycles_used'].mean()
        total_yearly_cycles = int(365 * avg_cycles_per_day)
        yearly_cycles = range(1, total_yearly_cycles + 1)
        yearly_capacities = [battery_capacity_mwh * (1 - degradation_per_cycle) ** (cycle - 1) for cycle in yearly_cycles]
        avg_daily_benefit_raw = daily_stats['daily_benefit'].mean()  # Before degradation
        yearly_benefit = sum([capacity * (avg_daily_benefit_raw / max(avg_cycles_per_day, 1)) for capacity in yearly_capacities])
    else:
        # For 1-cycle analysis, use 365 cycles
        yearly_cycles = range(1, 366)
        yearly_capacities = [battery_capacity_mwh * (1 - degradation_per_cycle) ** (cycle - 1) for cycle in yearly_cycles]
        avg_price_spread = daily_stats['daily_benefit'].mean()
        yearly_benefit = sum([capacity * avg_price_spread for capacity in yearly_capacities])
    
    # Calculate ROI metrics
    total_investment = battery_capacity_mwh * battery_cost_per_mwh
    roi_percentage = (yearly_benefit / total_investment * 100) if total_investment > 0 else 0
    payback_years = (total_investment / yearly_benefit) if yearly_benefit > 0 else float('inf')
    
    return {
        'total_benefit': total_benefit,
        'avg_daily_benefit': avg_daily_benefit,
        'yearly_benefit': yearly_benefit,
        'total_investment': total_investment,
        'roi_percentage': roi_percentage,
        'payback_years': payback_years,
        'total_days': len(daily_stats)
    }

def calculate_cycle_statistics(daily_stats, analysis_type):
    """Calculate cycle usage statistics"""
    if analysis_type == "2 Cycles":
        avg_cycles_per_day = daily_stats['cycles_used'].mean()
        total_cycles_used = daily_stats['cycles_used'].sum()
        days_with_2_cycles = len(daily_stats[daily_stats['cycles_used'] == 2])
        days_with_1_cycle = len(daily_stats[daily_stats['cycles_used'] == 1])
        days_with_no_cycles = len(daily_stats[daily_stats['cycles_used'] == 0])
        
        return {
            'avg_cycles_per_day': avg_cycles_per_day,
            'total_cycles_used': total_cycles_used,
            'days_with_2_cycles': days_with_2_cycles,
            'days_with_1_cycle': days_with_1_cycle,
            'days_with_no_cycles': days_with_no_cycles
        }
    else:
        feasible_days = len(daily_stats[daily_stats['arbitrage_possible'] == True])
        total_days = len(daily_stats)
        feasibility_percentage = (feasible_days / total_days * 100) if total_days > 0 else 0
        days_with_1_cycle = len(daily_stats[daily_stats['arbitrage_possible'] == True])
        days_with_no_cycles = len(daily_stats[daily_stats['arbitrage_possible'] == False])
        days_with_2_cycles = 0  # Not applicable for 1-cycle analysis
        
        return {
            'feasible_days': feasible_days,
            'feasibility_percentage': feasibility_percentage,
            'days_with_1_cycle': days_with_1_cycle,
            'days_with_no_cycles': days_with_no_cycles,
            'days_with_2_cycles': days_with_2_cycles
        }

def find_best_worst_days(daily_stats):
    """Find best and worst performing days"""
    if len(daily_stats) > 0:
        best_day_idx = daily_stats['degraded_benefit'].idxmax()
        worst_day_idx = daily_stats['degraded_benefit'].idxmin()
        
        return {
            'best_day_benefit': daily_stats.loc[best_day_idx, 'degraded_benefit'],
            'worst_day_benefit': daily_stats.loc[worst_day_idx, 'degraded_benefit'],
            'best_day_date': daily_stats.loc[best_day_idx, 'date'],
            'worst_day_date': daily_stats.loc[worst_day_idx, 'date']
        }
    
    return None