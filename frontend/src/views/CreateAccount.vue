<template>
  <v-content>
    <v-container fluid fill-height>
      <v-layout align-center justify-center>
        <v-flex xs12 sm8 md4>
          <v-card class="elevation-12">
            <v-toolbar dark color="primary">
              <v-toolbar-title>{{appName}}</v-toolbar-title>
              <v-spacer></v-spacer>
            </v-toolbar>
            <v-card-text>
              <v-form @keyup.enter="submit">
                <v-text-field @keyup.enter="submit" v-model="email" prepend-icon="person" name="login" label="Login email" type="text"></v-text-field>
                <v-text-field @keyup.enter="submit" v-model="invitecode" prepend-icon="lock" name="invitecode" label="Invite Code" id="invitecode" type="text"></v-text-field>
                <v-text-field @keyup.enter="submit" v-model="fullname" prepend-icon="person" name="fullname" label="Full Name" type="text"></v-text-field>
                <v-text-field @keyup.enter="submit" v-model="password" prepend-icon="lock" name="password" label="Password" id="password" type="password"></v-text-field>
                <v-text-field @keyup.enter="submit" v-model="passwordVerify" prepend-icon="lock" name="passwordVerify" label="Verify Password" id="passwordVerify" type="password"></v-text-field>
              </v-form>
              <div v-if="accountCreationError">
                <v-alert :value="accountCreationError" transition="fade-transition" type="error">
                  Invalid invite code, please contact support@pastel.network
                </v-alert>
              </div>
              <v-flex class="caption text-xs-right"><router-link to="/login">Already have an account? Login to it here.</router-link></v-flex>

            </v-card-text>
            <v-card-actions>
              <v-spacer></v-spacer>
              <v-btn @click.prevent="submit">Create Account</v-btn>
            </v-card-actions>
          </v-card>
        </v-flex>
      </v-layout>
    </v-container>
  </v-content>
</template>

<script lang="ts">
import { Component, Vue } from 'vue-property-decorator';
import { api } from '@/api';
import { appName } from '@/env';
import { readLoginError } from '@/store/main/getters';
import {dispatchCreateAccount, dispatchLogIn} from '@/store/main/actions';

@Component
export default class Login extends Vue {
  public email: string = '';
  public invitecode: string = '';
  public fullname: string = '';
  public password: string = '';
  public passwordVerify: string = '';

  public appName = appName;

  public get accountCreationError() {
    return readLoginError(this.$store);
  }

  public submit() {
    dispatchCreateAccount(this.$store, {email: this.email, fullname: this.fullname,  invitecode: this.invitecode, password: this.password});
  }
}
</script>

<style>
</style>
