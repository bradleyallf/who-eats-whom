import { getGreeting } from '../support/app.po';

describe('who-eats-whom', () => {
  beforeEach(() => cy.visit('/'));

  it('should display the main title', () => {
    getGreeting().contains('Who Eats Whom');
  });
});
