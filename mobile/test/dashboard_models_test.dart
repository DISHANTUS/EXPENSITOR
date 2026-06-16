import 'package:expensitor_mobile/core/format/money.dart';
import 'package:expensitor_mobile/features/home/dashboard_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('formatMoney', () {
    test('matches backend phrasing', () {
      expect(formatMoney('15000.0000', 'INR'), '₹15,000');
      expect(formatMoney('420.0000', 'INR'), '₹420');
      expect(formatMoney('420.00', 'USD'), '\$420');
      expect(formatMoney('1234567', 'EUR'), '€1,234,567');
      expect(formatMoney(null, 'INR'), '—');
      expect(formatMoney('900.00', 'XYZ'), 'XYZ 900');
    });
  });

  group('ProactiveFeed', () {
    final json = {
      'items': [
        {
          'kind': 'alert', 'category': 'dependency', 'title': 'A plan leans on late money',
          'what_happened': 'Depends on ₹15,000 on Jun 24.', 'why_it_matters': 'Could fall short.',
          'what_next': 'Confirm it.', 'most_useful_number': 'Amount riding on it: ₹15,000.',
          'severity': 'alert', 'priority': 0.92, 'evidence': {},
        },
        {
          'kind': 'warning', 'category': 'stress', 'title': 'Pressure building',
          'what_happened': '...', 'why_it_matters': '...', 'what_next': '...',
          'most_useful_number': null, 'severity': 'warning', 'priority': 0.7, 'evidence': {},
        },
      ],
      'most_important': {
        'kind': 'alert', 'category': 'dependency', 'title': 'A plan leans on late money',
        'what_happened': 'Depends on ₹15,000 on Jun 24.', 'why_it_matters': 'Could fall short.',
        'what_next': 'Confirm it.', 'most_useful_number': 'Amount riding on it: ₹15,000.',
        'severity': 'alert', 'evidence': {},
      },
    };

    test('parses headline + others split', () {
      final feed = ProactiveFeed.fromJson(json);
      expect(feed.mostImportant?.title, 'A plan leans on late money');
      expect(feed.items.length, 2);
      expect(feed.others.length, 1);
      expect(feed.others.single.category, 'stress');
    });

    test('cold-start empty feed', () {
      final feed = ProactiveFeed.fromJson({'items': [], 'most_important': null});
      expect(feed.mostImportant, isNull);
      expect(feed.others, isEmpty);
    });
  });

  test('DailyBrief parses context numbers + commentary', () {
    final b = DailyBrief.fromJson({
      'context': {
        'currency': 'INR', 'daily_remaining': '420.0000', 'weekly_remaining': '2500.0000',
        'monthly_discretionary_remaining': '6000.0000',
      },
      'commentary': {
        'deterministic_commentary': {
          'headline': "Here's where things stand.", 'paragraphs': ['p1', 'p2'], 'severity': 'info',
        },
      },
    });
    expect(b.currency, 'INR');
    expect(b.dailyRemaining, '420.0000');
    expect(b.headline, "Here's where things stand.");
    expect(b.paragraphs, ['p1', 'p2']);
  });

  test('HealthSummary parses score, drag, pillars, cold-start', () {
    final h = HealthSummary.fromJson({
      'overall_score': 62, 'overall_confidence': 'normal', 'overall_state': 'fair',
      'pillars': [
        {'key': 'cashflow', 'label': 'Cashflow', 'score': 44, 'state': 'fair'},
        {'key': 'resilience', 'label': 'Resilience', 'score': 70, 'state': 'fair'},
      ],
      'biggest_drag': {'statement': 'lifestyle inflation', 'pillar': 'discipline', 'contribution': -30},
      'top_strengths': ['Strong savings consistency'],
      'worsening_area': 'discipline',
    });
    expect(h.overallScore, 62);
    expect(h.isColdStart, isFalse);
    expect(h.biggestDrag, 'lifestyle inflation');
    expect(h.pillars.length, 2);
    expect(h.pillars.first.label, 'Cashflow');

    final cold = HealthSummary.fromJson({'overall_score': 50, 'overall_confidence': 'low', 'overall_state': 'fair', 'pillars': []});
    expect(cold.isColdStart, isTrue);
  });
}
