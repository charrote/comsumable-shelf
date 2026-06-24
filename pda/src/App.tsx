import React from 'react'
import { TouchableOpacity, StyleSheet } from 'react-native'
import { NavigationContainer, useNavigation } from '@react-navigation/native'
import { createNativeStackNavigator, NativeStackNavigationProp } from '@react-navigation/native-stack'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { StatusBar } from 'expo-status-bar'

import LoginScreen from './screens/LoginScreen'
import HomeScreen from './screens/HomeScreen'
import InboundScreen from './screens/InboundScreen'
import ShelvingScreen from './screens/ShelvingScreen'
import OutboundScreen from './screens/OutboundScreen'
import TrackingScreen from './screens/TrackingScreen'
import SettingsScreen from './screens/SettingsScreen'
import { useAuthStore } from './store/authStore'

import { HomeIcon, InboundIcon, ShelvingIcon, OutboundIcon, TrackingIcon, SettingsIcon } from './components/TabBarIcons'

export type RootStackParamList = {
  Login: undefined
  MainTabs: undefined
  Settings: undefined
}

export type MainTabParamList = {
  Home: undefined
  Inbound: undefined
  Shelving: undefined
  Outbound: undefined
  Tracking: undefined
}

const Stack = createNativeStackNavigator<RootStackParamList>()
const Tab = createBottomTabNavigator<MainTabParamList>()

const TAB_ICON_SIZE = 24

function SettingsHeaderButton() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  return (
    <TouchableOpacity
      style={styles.headerBtn}
      onPress={() => navigation.navigate('Settings')}
    >
      <SettingsIcon focused={false} color="#fff" size={22} />
    </TouchableOpacity>
  )
}

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#0066CC' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold', fontSize: 18 },
        headerRight: () => <SettingsHeaderButton />,
        tabBarActiveTintColor: '#0066CC',
        tabBarInactiveTintColor: '#999',
        tabBarStyle: {
          backgroundColor: '#fff',
          borderTopWidth: 1,
          borderTopColor: '#e8e8e8',
          paddingBottom: 6,
          paddingTop: 6,
          height: 60,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
        },
      }}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{
          title: '首页',
          tabBarLabel: '首页',
          tabBarIcon: ({ focused, color }) => (
            <HomeIcon focused={focused} color={color} size={TAB_ICON_SIZE} />
          ),
        }}
      />
      <Tab.Screen
        name="Inbound"
        component={InboundScreen}
        options={{
          headerShown: false,
          tabBarLabel: '收料入库',
          tabBarIcon: ({ focused, color }) => (
            <InboundIcon focused={focused} color={color} size={TAB_ICON_SIZE} />
          ),
        }}
      />
      <Tab.Screen
        name="Shelving"
        component={ShelvingScreen}
        options={{
          headerShown: false,
          tabBarLabel: '料盘上架',
          tabBarIcon: ({ focused, color }) => (
            <ShelvingIcon focused={focused} color={color} size={TAB_ICON_SIZE} />
          ),
        }}
      />
      <Tab.Screen
        name="Outbound"
        component={OutboundScreen}
        options={{
          headerShown: false,
          tabBarLabel: '扫码出库',
          tabBarIcon: ({ focused, color }) => (
            <OutboundIcon focused={focused} color={color} size={TAB_ICON_SIZE} />
          ),
        }}
      />
      <Tab.Screen
        name="Tracking"
        component={TrackingScreen}
        options={{
          title: '库存跟踪',
          tabBarLabel: '库存跟踪',
          tabBarIcon: ({ focused, color }) => (
            <TrackingIcon focused={focused} color={color} size={TAB_ICON_SIZE} />
          ),
        }}
      />
    </Tab.Navigator>
  )
}

export default function App() {
  const token = useAuthStore((s) => s.token)

  return (
    <NavigationContainer>
      <StatusBar style={token ? 'light' : 'dark'} />
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {token ? (
          <>
            <Stack.Screen name="MainTabs" component={MainTabs} />
            <Stack.Screen
              name="Settings"
              component={SettingsScreen}
              options={{
                headerShown: true,
                title: '设置',
                headerStyle: { backgroundColor: '#0066CC' },
                headerTintColor: '#fff',
                headerTitleStyle: { fontWeight: 'bold', fontSize: 18 },
                presentation: 'modal',
              }}
            />
          </>
        ) : (
          <Stack.Screen name="Login" component={LoginScreen} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  )
}

const styles = StyleSheet.create({
  headerBtn: {
    paddingHorizontal: 16,
    paddingVertical: 4,
  },
})
