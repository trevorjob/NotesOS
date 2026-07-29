import React, { useMemo, useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '@/theme/ThemeProvider';
import { COUNTRIES, Country } from '@/lib/countries';

// Phone input with an explicit country/dial-code picker. The country is chosen by
// the user (never guessed from the device), so a foreign national number can't be
// mis-parsed — see lib/phone.ts composeE164 for the "why". The parent owns the
// composed value; this component owns the two pieces (country + national number).
interface PhoneInputProps {
  label?: string;
  country: Country;
  nationalNumber: string;
  onChangeCountry: (country: Country) => void;
  onChangeNationalNumber: (value: string) => void;
  autoFocus?: boolean;
}

export function PhoneInput({
  label,
  country,
  nationalNumber,
  onChangeCountry,
  onChangeNationalNumber,
  autoFocus,
}: PhoneInputProps) {
  const { c, font, size, radius, trackingUtility } = useTheme();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [focused, setFocused] = useState(false);
  const [query, setQuery] = useState('');

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return COUNTRIES;
    return COUNTRIES.filter(
      (ctry) =>
        ctry.name.toLowerCase().includes(q) ||
        ctry.code.toLowerCase().includes(q) ||
        ctry.dialCode.includes(q.replace('+', '')),
    );
  }, [query]);

  const selectCountry = (next: Country) => {
    onChangeCountry(next);
    setPickerOpen(false);
    setQuery('');
  };

  return (
    <View style={{ gap: 6 }}>
      {label && (
        <Text style={{ fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: c.inkSecondary }}>
          {label}
        </Text>
      )}

      <View
        style={[
          styles.row,
          { borderRadius: radius.sm, borderColor: focused ? c.ink : c.paperEdge, backgroundColor: c.paper },
        ]}
      >
        <Pressable onPress={() => setPickerOpen(true)} style={[styles.codeButton, { borderRightColor: c.paperEdge }]}>
          <Text style={{ fontSize: size.body }}>{country.flag}</Text>
          <Text style={{ fontFamily: font.body, fontSize: size.body, color: c.ink }}>+{country.dialCode}</Text>
          <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>▼</Text>
        </Pressable>

        <TextInput
          value={nationalNumber}
          onChangeText={onChangeNationalNumber}
          placeholder="801 234 5678"
          placeholderTextColor={c.inkTertiary}
          keyboardType="phone-pad"
          autoFocus={autoFocus}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{ flex: 1, paddingHorizontal: 14, paddingVertical: 12, minHeight: 44, fontFamily: font.body, fontSize: size.body, color: c.ink }}
        />
      </View>

      <Modal visible={pickerOpen} animationType="slide" onRequestClose={() => setPickerOpen(false)}>
        <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingTop: 14, paddingBottom: 8 }}>
            <Text style={{ flex: 1, fontFamily: font.display, fontSize: size.display3, color: c.ink }}>Country</Text>
            <Pressable onPress={() => setPickerOpen(false)} style={{ minHeight: 44, minWidth: 44, alignItems: 'center', justifyContent: 'center' }}>
              <Text style={{ color: c.inkSecondary, fontSize: 20 }}>✕</Text>
            </Pressable>
          </View>

          <View style={{ paddingHorizontal: 16, paddingBottom: 8 }}>
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Search country or code"
              placeholderTextColor={c.inkTertiary}
              autoFocus
              style={{ borderWidth: 1, borderColor: c.paperEdge, borderRadius: radius.sm, paddingHorizontal: 14, paddingVertical: 12, minHeight: 44, fontFamily: font.body, fontSize: size.body, color: c.ink }}
            />
          </View>

          <FlatList
            data={results}
            keyExtractor={(item) => item.code}
            keyboardShouldPersistTaps="handled"
            renderItem={({ item }) => {
              const active = item.code === country.code;
              return (
                <Pressable
                  onPress={() => selectCountry(item)}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 12, minHeight: 44, borderBottomWidth: 1, borderBottomColor: c.paperEdge }}
                >
                  <Text style={{ fontSize: 20 }}>{item.flag}</Text>
                  <Text style={{ flex: 1, fontFamily: font.body, fontSize: size.body, color: active ? c.confirm : c.ink }}>{item.name}</Text>
                  <Text style={{ fontFamily: font.body, fontSize: size.bodySm, color: c.inkTertiary }}>+{item.dialCode}</Text>
                </Pressable>
              );
            }}
          />
        </SafeAreaView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', borderWidth: 1 },
  codeButton: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 12, minHeight: 44, borderRightWidth: 1 },
});
