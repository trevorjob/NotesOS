import React from 'react';
import { ScrollView, StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import { Edge, SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '@/theme/ThemeProvider';

interface ScreenProps {
  children: React.ReactNode;
  scroll?: boolean;
  contentStyle?: StyleProp<ViewStyle>;
  edges?: Edge[];
}

export function Screen({ children, scroll = true, contentStyle, edges = ['top', 'bottom', 'left', 'right'] }: ScreenProps) {
  const { c, space } = useTheme();
  const content = [styles.content, { padding: space.gutterPage }, contentStyle];

  return (
    <SafeAreaView style={[styles.root, { backgroundColor: c.paper }]} edges={edges}>
      {scroll ? (
        <ScrollView contentContainerStyle={content}>{children}</ScrollView>
      ) : (
        <View style={content}>{children}</View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  content: { flexGrow: 1, gap: 18 },
});
