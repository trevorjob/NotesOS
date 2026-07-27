import React from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface SheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

export function Sheet({ open, onClose, title, children }: SheetProps) {
  const { c, font, size, radius, hardShadow } = useTheme();

  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.root}>
        <Pressable style={[StyleSheet.absoluteFill, styles.scrim, { backgroundColor: c.ink }]} onPress={onClose} />
        <View
          style={[
            styles.sheet,
            { backgroundColor: c.paper, borderColor: c.paperEdge, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg },
            hardShadow(c.paperEdge, 4),
          ]}
        >
          <View style={[styles.handle, { backgroundColor: c.paperEdge, borderRadius: radius.pill }]} />
          {title && <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink, marginBottom: 12 }}>{title}</Text>}
          {children}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: 'flex-end' },
  scrim: { opacity: 0.25 },
  sheet: { borderTopWidth: 1, padding: 20, paddingBottom: 28, maxHeight: '80%' },
  handle: { width: 36, height: 4, alignSelf: 'center', marginBottom: 16 },
});
