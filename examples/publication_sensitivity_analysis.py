#!/usr/bin/env python3
"""Example script demonstrating sensitivity analysis for scientific publications.

This script shows how to use the new sensitivity analysis framework
to generate publication-ready results for Applied Energy or similar journals.

Usage:
    python examples/publication_sensitivity_analysis.py

Output:
    - Sensitivity analysis results table (Markdown format)
    - Sensitivity indices (parameter ranking)
    - Recommendations for publication discussion
"""

from __future__ import annotations

from energis.analysis import (
    create_standard_sensitivity_study,
    apply_parameter_variation,
    format_sensitivity_table,
    calculate_sensitivity_indices,
    SensitivityResult,
)


def example_optimization_function(config: dict) -> SensitivityResult:
    """Example optimization function (replace with actual implementation).

    In a real application, this would:
    1. Build the Pyomo model with the given configuration
    2. Solve the optimization problem
    3. Extract results (objective, key metrics)
    4. Return SensitivityResult

    Args:
        config: Configuration dictionary with parameter values

    Returns:
        SensitivityResult with objective and key metrics
    """
    # This is a simplified example - replace with actual optimization
    # For demonstration, we'll simulate some results

    # Extract some parameters to show realistic variation
    p2h_eff = config.get("generators", {}).get("p2h", {}).get("el_to_th_eff", 0.99)
    gas_price = config.get("fuels", {}).get("gas", {}).get("price_eur_mwh", 58.6)
    storage_loss = config.get("storage", {}).get("hourly_loss", 0.0005)

    # Simulate objective value (total cost) with realistic dependencies
    base_cost = 1_000_000.0  # Base annual cost in EUR

    # Cost increases with lower efficiency (need more fuel)
    eff_factor = 0.99 / p2h_eff  # Inverse relationship

    # Cost proportional to fuel price
    price_factor = gas_price / 58.6

    # Cost increases slightly with storage losses
    loss_factor = 1.0 + (storage_loss - 0.0005) * 100

    total_cost = base_cost * eff_factor * price_factor * loss_factor

    # Simulate other key metrics
    co2_emissions = total_cost * 0.2  # Rough correlation
    renewable_share = 0.30 - (gas_price / 58.6 - 1.0) * 0.05  # More gas = less renewable

    return SensitivityResult(
        param_path="",  # Will be filled by sensitivity analysis
        param_value=0.0,  # Will be filled
        variation_label="",  # Will be filled
        objective_value=total_cost,
        key_metrics={
            "total_cost_eur": total_cost,
            "co2_emissions_kg": co2_emissions,
            "renewable_share": max(0.0, min(1.0, renewable_share)),
        },
        solve_status="optimal",
    )


def main():
    """Run sensitivity analysis and generate publication outputs."""

    print("=" * 80)
    print("SENSITIVITY ANALYSIS FOR SCIENTIFIC PUBLICATION")
    print("=" * 80)
    print()

    # Create base configuration (simplified example)
    base_config = {
        "generators": {
            "p2h": {
                "el_to_th_eff": 0.99,
            }
        },
        "fuels": {
            "gas": {
                "price_eur_mwh": 58.6,
            }
        },
        "storage": {
            "hourly_loss": 0.0005,
            "eff_charge": 0.98,
            "eff_discharge": 0.98,
        },
        "heat_pumps": {
            "types": {
                "standard": {
                    "eta": 0.75,
                }
            }
        },
        "electricity": {
            "price_eur_mwh": 50.0,
        },
    }

    # Create standard sensitivity study
    print("Creating standard sensitivity study...")
    variations = create_standard_sensitivity_study()
    print(f"  → {len(variations)} parameter variations defined")
    print()

    # Run sensitivity analysis for each parameter
    print("Running sensitivity analysis...")
    print()

    results_by_param = {}

    for i, variation in enumerate(variations, 1):
        print(f"[{i}/{len(variations)}] Analyzing: {variation.description}")
        param_results = []

        param_values = variation.get_values()
        param_labels = variation.get_labels()

        for value, label in zip(param_values, param_labels):
            # Apply parameter variation
            try:
                modified_config = apply_parameter_variation(
                    base_config, variation.param_path, value
                )

                # Run optimization
                result = example_optimization_function(modified_config)

                # Fill in metadata
                result.param_path = variation.param_path
                result.param_value = value
                result.variation_label = label

                param_results.append(result)

                print(f"  {label:20s} → Cost: {result.objective_value:,.0f} EUR")

            except KeyError as e:
                print(f"  {label:20s} → Parameter not found in config: {e}")
                # For demonstration, continue with other parameters
                continue

        results_by_param[variation.param_path] = param_results
        print()

    # Generate publication-ready table
    print("=" * 80)
    print("RESULTS: SENSITIVITY TABLE (Markdown format)")
    print("=" * 80)
    print()

    if results_by_param:
        table = format_sensitivity_table(
            results_by_param, metric_name="total_cost_eur", format_spec=",.0f"
        )
        print(table)
        print()

        # Calculate sensitivity indices
        print("=" * 80)
        print("SENSITIVITY INDICES (Parameter Ranking)")
        print("=" * 80)
        print()

        indices = calculate_sensitivity_indices(
            results_by_param, metric_name="total_cost_eur"
        )

        if indices:
            print("Ranking (higher = more sensitive):")
            print()
            for rank, (param, index) in enumerate(
                sorted(indices.items(), key=lambda x: x[1], reverse=True), 1
            ):
                param_short = param.split(".")[-1]
                print(f"  {rank}. {param_short:25s} : {index:.4f}")
            print()

            # Provide publication recommendations
            print("=" * 80)
            print("RECOMMENDATIONS FOR PUBLICATION")
            print("=" * 80)
            print()
            print("Based on the sensitivity analysis results:")
            print()

            # Find most sensitive parameter
            most_sensitive = max(indices.items(), key=lambda x: x[1])
            param_name = most_sensitive[0].split(".")[-1]
            sensitivity = most_sensitive[1]

            if sensitivity > 0.05:
                print(
                    f"1. HIGH SENSITIVITY: '{param_name}' shows significant impact "
                    f"({sensitivity:.1%} variation)."
                )
                print(
                    "   → Recommendation: Discuss parameter uncertainty in limitations section."
                )
                print("   → Recommendation: Validate parameter value with multiple sources.")
            else:
                print(
                    f"1. ROBUST RESULTS: Maximum sensitivity is {sensitivity:.1%}, "
                    "indicating robust conclusions."
                )
                print(
                    "   → Recommendation: Emphasize robustness in discussion section."
                )

            print()
            print(
                "2. SUGGESTED TEXT FOR METHODS SECTION:"
            )
            print()
            print(
                '   "Sensitivity analysis was performed by varying key parameters'
            )
            print(
                '    within realistic uncertainty ranges: ±3-5% for component efficiencies,'
            )
            print(
                '    ±20% for energy prices, and ±50% for storage loss rates. The analysis'
            )
            print(
                '    confirms that system design conclusions remain valid across all'
            )
            print('    tested parameter ranges."')
            print()

        else:
            print("No sensitivity indices calculated (not enough valid results).")
            print()

    else:
        print("No results to display.")
        print()

    print("=" * 80)
    print("NEXT STEPS FOR PUBLICATION")
    print("=" * 80)
    print()
    print("1. Replace example_optimization_function() with actual model")
    print("2. Run sensitivity analysis with real data")
    print("3. Generate plots:")
    print("   - Tornado diagram (one-at-a-time sensitivity)")
    print("   - Parameter impact bar chart")
    print("4. Include results in manuscript:")
    print("   - Table in Methods or Results section")
    print("   - Discussion of parameter impacts")
    print("   - Validation of assumptions")
    print()
    print("See docs/PUBLICATION_READY_METHODS.md for complete methodology.")
    print()


if __name__ == "__main__":
    main()
