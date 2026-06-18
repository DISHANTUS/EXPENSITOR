import 'package:flutter/material.dart';

/// Single-select option chips with an "Other (I don't see my option)" affordance
/// that reveals a text field. Reports either a known option or the custom text —
/// "Other" is NEVER the stored value. Used across every choice flow.
class OtherableChips extends StatefulWidget {
  const OtherableChips({
    super.key,
    required this.options,
    required this.onChanged,
    this.initialValue,
    this.otherLabel = 'Other (I don’t see my option)',
    this.customHint = 'Type it here',
  });

  /// Known options (display == value).
  final List<String> options;

  /// Called with the chosen value and whether it's a custom (typed) value.
  final void Function(String value, bool isCustom) onChanged;
  final String? initialValue;
  final String otherLabel;
  final String customHint;

  @override
  State<OtherableChips> createState() => _OtherableChipsState();
}

class _OtherableChipsState extends State<OtherableChips> {
  late String? _selected = widget.initialValue;
  bool _otherMode = false;
  final _custom = TextEditingController();

  @override
  void initState() {
    super.initState();
    // If the initial value isn't a known option, it's a pre-existing custom.
    if (widget.initialValue != null && !widget.options.contains(widget.initialValue)) {
      _otherMode = true;
      _custom.text = widget.initialValue!;
      _selected = null;
    }
  }

  @override
  void dispose() {
    _custom.dispose();
    super.dispose();
  }

  void _pickKnown(String value) {
    setState(() {
      _selected = value;
      _otherMode = false;
    });
    widget.onChanged(value, false);
  }

  void _pickOther() {
    setState(() {
      _selected = null;
      _otherMode = true;
    });
    // Emit current custom text (may be empty until typed).
    widget.onChanged(_custom.text.trim(), true);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final o in widget.options)
              ChoiceChip(label: Text(o), selected: _selected == o, onSelected: (_) => _pickKnown(o)),
            ChoiceChip(
              label: Text(widget.otherLabel),
              selected: _otherMode,
              onSelected: (_) => _pickOther(),
            ),
          ],
        ),
        if (_otherMode) ...[
          const SizedBox(height: 12),
          TextField(
            controller: _custom,
            autofocus: true,
            decoration: InputDecoration(labelText: widget.customHint),
            onChanged: (v) => widget.onChanged(v.trim(), true),
          ),
        ],
      ],
    );
  }
}
