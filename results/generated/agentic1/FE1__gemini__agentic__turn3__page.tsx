'use client';

import { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import CircularProgress from '@mui/material/CircularProgress';
import Grid from '@mui/material/Grid';
import { apiRequest } from '@/lib/api-client';
import { Budget } from '@/components/dashboard/overview/budget';
import { TotalCustomers } from '@/components/dashboard/overview/total-customers';
import { TasksProgress } from '@/components/dashboard/overview/tasks-progress';
import { TotalProfit } from '@/components/dashboard/overview/total-profit';
import { Sales } from '@/components/dashboard/overview/sales';
import { Traffic } from '@/components/dashboard/overview/traffic';
import { LatestProducts } from '@/components/dashboard/overview/latest-products';
import { LatestOrders } from '@/components/dashboard/overview/latest-orders';

interface DashboardSummary {
  budget?: string | number;
  totalCustomers?: string | number;
  tasksProgress?: number;
  totalProfit?: string | number;
  sales?: any;
  traffic?: any;
  recentProducts?: any[];
  recentTransactions?: any[];
  latestProducts?: any[];
  latestOrders?: any[];
  [key: string]: any;
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    async function fetchDashboardSummary() {
      try {
        setIsLoading(true);
        const data = await apiRequest('/dashboard/summary');
        if (isMounted && data) {
          setSummary(data);
        }
      } catch (error) {
        console.error('Failed to fetch dashboard summary:', error);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    fetchDashboardSummary();

    return () => {
      isMounted = false;
    };
  }, []);

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '60vh',
          width: '100%',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  const recentProducts = Array.isArray(summary?.recentProducts)
    ? summary.recentProducts
    : Array.isArray(summary?.latestProducts)
    ? summary.latestProducts
    : [];

  const recentTransactions = Array.isArray(summary?.recentTransactions)
    ? summary.recentTransactions
    : Array.isArray(summary?.latestOrders)
    ? summary.latestOrders
    : [];

  const salesSeries = summary?.sales?.chartSeries ?? (Array.isArray(summary?.sales) ? summary.sales : []);
  const trafficSeries = summary?.traffic?.chartSeries ?? (Array.isArray(summary?.traffic) ? summary.traffic : []);
  const trafficLabels = summary?.traffic?.labels;

  return (
    <Box
      component="main"
      sx={{
        flexGrow: 1,
        py: 4,
      }}
    >
      <Container maxWidth="xl">
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <Budget
              difference={12}
              trend="up"
              sx={{ height: '100%' }}
              value={summary?.budget}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <TotalCustomers
              difference={16}
              trend="down"
              sx={{ height: '100%' }}
              value={summary?.totalCustomers}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <TasksProgress
              sx={{ height: '100%' }}
              value={summary?.tasksProgress}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <TotalProfit
              sx={{ height: '100%' }}
              value={summary?.totalProfit}
            />
          </Grid>

          <Grid size={{ xs: 12, lg: 8 }}>
            <Sales
              chartSeries={salesSeries}
              sx={{ height: '100%' }}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 4 }}>
            <Traffic
              chartSeries={trafficSeries}
              labels={trafficLabels}
              sx={{ height: '100%' }}
            />
          </Grid>

          <Grid size={{ xs: 12, md: 6, lg: 4 }}>
            <LatestProducts products={recentProducts} sx={{ height: '100%' }} />
          </Grid>
          <Grid size={{ xs: 12, md: 12, lg: 8 }}>
            <LatestOrders orders={recentTransactions} sx={{ height: '100%' }} />
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
}
