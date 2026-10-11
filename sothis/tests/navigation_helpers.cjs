// Exercise the single global entry through Home when the current screen owns a query.
exports.openSearch=async function(page){
 if(await page.evaluate(()=>state.tab==='search'))return;
 const search=page.locator('.nav [data-tab=search]');
 if(!await search.isVisible())await page.locator('.nav [data-tab=home]').click();
 await search.click();
};
