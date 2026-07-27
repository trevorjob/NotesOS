import { useFonts } from 'expo-font';
import { Stack, usePathname } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavFab } from '@/components/nav/NavFab';
import { QuickSwitcher } from '@/components/nav/QuickSwitcher';
import { QuickSwitcherProvider } from '@/components/nav/QuickSwitcherContext';
import { fontsToLoad } from '@/theme/fonts';
import { ThemeProvider } from '@/theme/ThemeProvider';

SplashScreen.preventAutoHideAsync();

// Screens where the global nav FAB doesn't apply yet — there's no "home" to jump to.
const NAV_FAB_HIDDEN_ROUTES = ['/login', '/onboarding', '/contacts', '/'];

function GlobalNav() {
  const pathname = usePathname();
  if (NAV_FAB_HIDDEN_ROUTES.includes(pathname)) return null;
  return <NavFab />;
}

export default function RootLayout() {
  const [loaded] = useFonts(fontsToLoad);

  useEffect(() => {
    if (loaded) SplashScreen.hideAsync();
  }, [loaded]);

  if (!loaded) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ThemeProvider>
          <QuickSwitcherProvider>
            <StatusBar style="auto" />
            <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: 'transparent' } }}>
              <Stack.Screen name="index" />
              <Stack.Screen name="login" />
              <Stack.Screen name="onboarding" />
              <Stack.Screen name="contacts" />
              <Stack.Screen name="home" />
              <Stack.Screen name="note" />
              <Stack.Screen name="retrieval" />
              <Stack.Screen name="voice" />
              <Stack.Screen name="capture" options={{ presentation: 'modal' }} />
              <Stack.Screen name="testbuilder" options={{ presentation: 'modal' }} />
              <Stack.Screen name="courses" />
              <Stack.Screen name="topics" />
              <Stack.Screen name="coursecreate" options={{ presentation: 'modal' }} />
              <Stack.Screen name="coursejoin" options={{ presentation: 'modal' }} />
              <Stack.Screen name="discovery" />
              <Stack.Screen name="settings" />
              <Stack.Screen name="notifications" />
              <Stack.Screen name="listen" />
              <Stack.Screen name="source" />
            </Stack>
            <GlobalNav />
            <QuickSwitcher />
          </QuickSwitcherProvider>
        </ThemeProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
