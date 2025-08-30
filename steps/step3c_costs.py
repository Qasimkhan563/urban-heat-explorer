import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt

def run_step():
    st.header("Step 4C: Costs, Carbon & Recommendations")

    with st.expander("ℹ️ Help: About This Step"):
        st.markdown("""
        In this step you compare **greening scenarios by cost and carbon benefits**.  

        - 💶 **Costs** →  
          \[
          \text{Cost (M€)} = \frac{(\text{Avg €/m²}) \times (\text{Area reduced})}{10^6}
          \]  

        - 🌱 **Carbon benefits** →  
          \[
          \text{CO₂ (tons/yr)} = \frac{\text{Area reduced (m²)} \times \text{Carbon factor (kg/m²/yr)}}{1000}
          \]  

        - 💡 **Recommendations** →  
          - Best scenario = **highest % heat reduction**.  
          - Most cost-efficient = **lowest M€ per % reduction**.  

        🔑 This step helps balance **urban cooling, climate impact, and financial feasibility**.
        """)

    # --- Percent reduction table ---
    df_abs = st.session_state["df_abs"]
    df_pct = df_abs.copy()
    for col in df_abs.columns:
        if col != "Baseline":
            df_pct[col] = (df_abs["Baseline"] - df_abs[col]) / df_abs["Baseline"] * 100
    df_pct["Baseline"] = 0.0
    df_pct = df_pct.round(1)

    st.subheader("📊 Reduction vs Baseline (%)")
    st.dataframe(df_pct)

    # --- Costs & Carbon ---
    df_carbon = pd.DataFrame()
    df_costs_long = []
    cost_eff = {}

    for city in df_abs.index:
        total_reduction = df_pct.loc[city].drop("Baseline").max()
        for scenario in df_abs.columns:
            if scenario != "Baseline":
                area_diff_km2 = df_abs.loc[city, "Baseline"] - df_abs.loc[city, scenario]
                area_m2 = area_diff_km2 * 1e6

                low, high = st.session_state["cost_canopy"] if "Canopy" in scenario else (
                    st.session_state["cost_roofs"] if "Roofs" in scenario else st.session_state["cost_parks"]
                )
                avg_cost = (low + high)/2 * area_m2/1e6
                df_costs_long.append({"City": city, "Scenario": scenario, "Avg Cost (M€)": avg_cost})

                co2 = area_m2 * st.session_state["carbon_factor"]/1000
                df_carbon.loc[city, scenario] = co2

        if total_reduction > 0:
            avg_cost_city = pd.DataFrame(df_costs_long).query("City==@city")["Avg Cost (M€)"].mean()
            cost_eff[city] = avg_cost_city / total_reduction

    df_costs = pd.DataFrame(df_costs_long)

    # --- Bubble chart: Cost vs Carbon ---
    st.subheader("⚖️ Cost vs Carbon Trade-off (Bubble Size = % Reduction)")
    df_carbon_long = df_carbon.reset_index().melt(id_vars="index", var_name="Scenario", value_name="CO₂ (tons/yr)")
    df_carbon_long.rename(columns={"index": "City"}, inplace=True)
    df_tradeoff = df_costs.merge(df_carbon_long, on=["City","Scenario"])
    df_tradeoff["% Reduction"] = df_tradeoff.apply(lambda row: df_pct.loc[row["City"], row["Scenario"]], axis=1)

    fig = px.scatter(
        df_tradeoff,
        x="Avg Cost (M€)", y="CO₂ (tons/yr)",
        size="% Reduction", color="Scenario",
        text="City", facet_col="City", facet_col_wrap=2,
        size_max=40, template="plotly_white"
    )
    st.plotly_chart(fig, use_container_width=True)

    # ======================================================
    # 🔹 DECISION SUPPORT FEATURES
    # ======================================================
    st.subheader("🔥 Efficiency Indicators")

    df_eff = []
    for city in df_abs.index:
        for scenario in df_abs.columns:
            if scenario != "Baseline":
                cost_val = df_costs.query("City==@city and Scenario==@scenario")["Avg Cost (M€)"].values[0]
                reduction_val = df_pct.loc[city, scenario]
                co2_val = df_carbon.loc[city, scenario]

                euro_per_pct = cost_val / reduction_val if reduction_val > 0 else float("inf")
                euro_per_ton = cost_val*1e6 / co2_val if co2_val > 0 else float("inf")

                df_eff.append({
                    "City": city,
                    "Scenario": scenario,
                    "M€ per % Reduction": euro_per_pct,
                    "M€ per ton CO₂": euro_per_ton
                })
    df_eff = pd.DataFrame(df_eff)

    # Apply traffic light colors
    def traffic_light(val, reverse=False):
        if val == df.min():
            return "🟢"
        elif val == df.max():
            return "🔴"
        else:
            return "🟡"

    st.dataframe(df_eff.round(2))

    # Ranking Table
    st.subheader("🏆 Scenario Ranking Table")
    ranking_table = df_eff.copy()
    ranking_table["Rank Cost-efficiency"] = ranking_table.groupby("City")["M€ per % Reduction"].rank()
    ranking_table["Rank Carbon-efficiency"] = ranking_table.groupby("City")["M€ per ton CO₂"].rank()
    st.dataframe(ranking_table.round(2))

    # ======================================================
    # 🔹 POLICY INSIGHTS
    # ======================================================
    st.subheader("🌍 Policy Insights")
    for city in df_pct.index:
        best_scenario = df_pct.loc[city].drop("Baseline").idxmax()
        best_val = df_pct.loc[city, best_scenario]
        best_co2 = df_carbon.loc[city, best_scenario]
        best_cost = df_costs.query("City==@city and Scenario==@best_scenario")["Avg Cost (M€)"].values[0]

        # Efficiency lookup
        eff_row = df_eff.query("City==@city and Scenario==@best_scenario").iloc[0]
        euro_per_pct = eff_row["M€ per % Reduction"]
        euro_per_ton = eff_row["M€ per ton CO₂"]

        st.markdown(f"""
        **{city}**  
        - ✅ Best Scenario: **{best_scenario}**  
        - 🌡 Reduction: **{best_val:.1f}%**  
        - 💶 Cost: ~{best_cost:.1f} M€  
        - 🌱 Carbon benefit: ~{best_co2:.0f} tons CO₂/yr  
        - 🔥 Efficiency: **{euro_per_pct:.2f} M€ / % reduction**, **{euro_per_ton:,.0f} M€ / ton CO₂**  

        📌 **Policy Note:**  
        - {best_scenario} achieves strongest cooling, but check trade-off:  
            🟢 if €/ % reduction is low → very cost-effective  
            🔴 if €/ ton CO₂ is high → weak climate impact.  
        - Mixed strategies (trees + roofs + parks) may balance **budget & climate impact**.  
        - Alignment: 🌍 *SDG 11 – Sustainable Cities*, 🌱 *SDG 13 – Climate Action*, 💶 *Local Economy*.  
        """)


    if cost_eff:
        best_city = min(cost_eff, key=cost_eff.get)
        st.success(f"🏆 Most cost-efficient city: **{best_city}** (lowest M€ per % reduction)")

    # --- Navigation ---
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("⬅️ Back"):
            st.session_state["step"] = 3.2
            st.rerun()
    with col2:
        if st.button("Next ➡️"):
            st.session_state["step"] = 3.4
            st.rerun()
