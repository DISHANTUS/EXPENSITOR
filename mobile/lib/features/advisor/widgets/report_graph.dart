import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../chat_models.dart';

/// Spending vs income over the report period (red = spent, green = income).
class ReportGraph extends StatelessWidget {
  const ReportGraph(this.series, {super.key});
  final GraphSeries series;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final pts = series.points;
    if (pts.isEmpty) {
      return const SizedBox(height: 60, child: Center(child: Text('No data for this period')));
    }
    List<FlSpot> spots(double Function(GraphPoint) f) =>
        [for (var i = 0; i < pts.length; i++) FlSpot(i.toDouble(), f(pts[i]))];

    final spent = cs.error;
    final income = Colors.green.shade600;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: 170,
          child: LineChart(
            LineChartData(
              gridData: const FlGridData(show: false),
              borderData: FlBorderData(show: false),
              lineTouchData: const LineTouchData(enabled: false),
              titlesData: FlTitlesData(
                leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 22,
                    interval: 1,
                    getTitlesWidget: (value, meta) {
                      final i = value.toInt();
                      // Thin out labels when there are many points.
                      final step = (pts.length / 6).ceil().clamp(1, pts.length);
                      if (i < 0 || i >= pts.length || i % step != 0) return const SizedBox.shrink();
                      return Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(pts[i].label, style: const TextStyle(fontSize: 9)),
                      );
                    },
                  ),
                ),
              ),
              lineBarsData: [
                LineChartBarData(spots: spots((p) => p.spent), isCurved: true, color: spent, barWidth: 2,
                    dotData: const FlDotData(show: false)),
                LineChartBarData(spots: spots((p) => p.income), isCurved: true, color: income, barWidth: 2,
                    dotData: const FlDotData(show: false)),
              ],
            ),
          ),
        ),
        const SizedBox(height: 6),
        Row(children: [
          _legendDot(spent), const SizedBox(width: 4), const Text('Spent', style: TextStyle(fontSize: 11)),
          const SizedBox(width: 16),
          _legendDot(income), const SizedBox(width: 4), const Text('Income', style: TextStyle(fontSize: 11)),
        ]),
      ],
    );
  }

  Widget _legendDot(Color c) =>
      Container(width: 10, height: 10, decoration: BoxDecoration(color: c, shape: BoxShape.circle));
}
