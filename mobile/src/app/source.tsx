import React, { useCallback, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { TopicResource, fetchTopicResources } from '@/lib/resources';

function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
    return err.response.data.detail;
  }
  return 'Couldn’t load the originals. Go back and try again.';
}

// Row title falls back through title → file name → a generic label.
function resourceLabel(resource: TopicResource): string {
  return resource.title || resource.file_name || 'Untitled source';
}

export default function SourceScreen() {
  const { c, font, size, space, trackingUtility, lineHeight } = useTheme();
  const { topicId } = useLocalSearchParams<{ topicId?: string }>();

  const [resources, setResources] = useState<TopicResource[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (!topicId) {
        setError('No topic selected.');
        setLoading(false);
        return;
      }
      let alive = true;
      (async () => {
        try {
          const page = await fetchTopicResources(topicId);
          if (!alive) return;
          setResources(page.resources);
          setError(null);
        } catch (err) {
          if (alive) setError(readError(err));
        } finally {
          if (alive) setLoading(false);
        }
      })();
      return () => {
        alive = false;
      };
    }, [topicId])
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10 }}>
        <Pressable onPress={() => router.back()} style={{ minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Note</Text>
        </Pressable>
        <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink, marginTop: 4 }}>Read the original</Text>
      </View>

      {loading ? (
        <View style={{ paddingTop: 60, alignItems: 'center', gap: 14 }}>
          <ActivityIndicator color={c.ink} />
          <Text style={{ color: c.inkSecondary, fontSize: size.body }}>Loading the originals…</Text>
        </View>
      ) : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
          {error && (
            <Text style={{ color: c.stateShaky, fontSize: size.bodySm, marginTop: 14 }}>{error}</Text>
          )}

          {!error && resources.length === 0 && (
            <Text style={{ color: c.inkTertiary, fontSize: size.body, paddingVertical: 24 }}>
              Nothing here yet — the raw sources appear once material is added to this topic.
            </Text>
          )}

          {resources.map((resource) => {
            const isOpen = openId === resource.id;
            return (
              <View key={resource.id}>
                <Pressable
                  onPress={() => setOpenId(isOpen ? null : resource.id)}
                  style={{
                    paddingVertical: 12,
                    borderBottomWidth: 1,
                    borderBottomColor: c.paperEdge,
                    minHeight: 44,
                    flexDirection: 'row',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 12,
                  }}
                >
                  <Text style={{ fontWeight: '600', color: c.ink, flex: 1 }}>{resourceLabel(resource)}</Text>
                  {resource.quarantined && (
                    <Text
                      style={{
                        fontFamily: font.utility,
                        fontSize: size.caption,
                        letterSpacing: trackingUtility(size.caption),
                        textTransform: 'uppercase',
                        color: c.inkTertiary,
                      }}
                    >
                      Held · only you
                    </Text>
                  )}
                </Pressable>
                {isOpen && (
                  <View style={{ paddingVertical: 12, gap: 8 }}>
                    {resource.needs_review && (
                      <Text style={{ fontSize: size.caption, color: c.stateFading }}>
                        Hard to read — worth a check.
                      </Text>
                    )}
                    <Text style={{ color: c.inkSecondary, fontSize: size.bodySm, lineHeight: size.bodySm * lineHeight.body }}>
                      {resource.content?.trim() || 'No text captured for this source yet.'}
                    </Text>
                    <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>
                      Added by {resource.uploader_name}
                    </Text>
                  </View>
                )}
              </View>
            );
          })}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
