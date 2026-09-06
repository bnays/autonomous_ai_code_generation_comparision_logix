'use client';

import * as React from 'react';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import Checkbox from '@mui/material/Checkbox';
import Divider from '@mui/material/Divider';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormGroup from '@mui/material/FormGroup';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { apiRequest } from 'src/utils/api-request';

export function Notifications(): React.JSX.Element {
  const [preferences, setPreferences] = React.useState({
    emailProductUpdates: true,
    emailSecurityUpdates: false,
    phoneProductUpdates: true,
    phoneSecurityUpdates: false,
  });

  const [isSaving, setIsSaving] = React.useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      await apiRequest('/users/notification-preferences', {
        method: 'PUT',
        body: JSON.stringify(preferences),
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <Card>
        <CardHeader subheader="Manage the notifications" title="Notifications" />
        <Divider />
        <CardContent>
          <Grid container spacing={6} wrap="wrap">
            <Grid
              size={{
                md: 4,
                sm: 6,
                xs: 12,
              }}
            >
              <Stack spacing={1}>
                <Typography variant="h6">Email</Typography>
                <FormGroup>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={preferences.emailProductUpdates}
                        onChange={(e) =>
                          setPreferences((prev) => ({
                            ...prev,
                            emailProductUpdates: e.target.checked,
                          }))
                        }
                      />
                    }
                    label="Product updates"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={preferences.emailSecurityUpdates}
                        onChange={(e) =>
                          setPreferences((prev) => ({
                            ...prev,
                            emailSecurityUpdates: e.target.checked,
                          }))
                        }
                      />
                    }
                    label="Security updates"
                  />
                </FormGroup>
              </Stack>
            </Grid>
            <Grid
              size={{
                md: 4,
                sm: 6,
                xs: 12,
              }}
            >
              <Stack spacing={1}>
                <Typography variant="h6">Phone</Typography>
                <FormGroup>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={preferences.phoneProductUpdates}
                        onChange={(e) =>
                          setPreferences((prev) => ({
                            ...prev,
                            phoneProductUpdates: e.target.checked,
                          }))
                        }
                      />
                    }
                    label="Email"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={preferences.phoneSecurityUpdates}
                        onChange={(e) =>
                          setPreferences((prev) => ({
                            ...prev,
                            phoneSecurityUpdates: e.target.checked,
                          }))
                        }
                      />
                    }
                    label="Security updates"
                  />
                </FormGroup>
              </Stack>
            </Grid>
          </Grid>
        </CardContent>
        <Divider />
        <CardActions sx={{ justifyContent: 'flex-end' }}>
          <Button type="submit" variant="contained" disabled={isSaving}>
            Save changes
          </Button>
        </CardActions>
      </Card>
    </form>
  );
}
